"""Public website and app-template regressions without database access.

Run with ``python manage.py test website``. SimpleTestCase forbids database
queries; authenticated template checks use an unsaved user and supplied context.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.http import FileResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import Resolver404, resolve, reverse

from . import views


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class PublicWebsiteTests(SimpleTestCase):
    pages = (
        ("home", "/", "website/home.html"),
        ("guide", "/huong-dan/", "website/guide.html"),
        ("privacy", "/chinh-sach-bao-mat/", "website/privacy.html"),
        ("account_deletion", "/xoa-tai-khoan/", "website/account_deletion.html"),
        ("download", "/tai-ung-dung/", "website/download.html"),
    )

    def test_crawler_files_list_only_public_pages(self):
        robots = self.client.get(reverse("website:robots_txt"))
        self.assertEqual(robots.status_code, 200)
        self.assertTrue(robots["Content-Type"].startswith("text/plain"))
        self.assertContains(robots, "Sitemap: https://gradeflow.io.vn/sitemap.xml")

        sitemap = self.client.get(reverse("website:sitemap"))
        self.assertEqual(sitemap.status_code, 200)
        self.assertTrue(sitemap["Content-Type"].startswith("application/xml"))
        for _, path, _ in self.pages:
            self.assertContains(sitemap, f"<loc>https://gradeflow.io.vn{path}</loc>")
        self.assertNotContains(sitemap, "/dashboard/")
        self.assertNotContains(sitemap, "/accounts/")

    def test_privacy_is_public_and_does_not_execute_ads_or_consent_scripts(self):
        response = self.client.get(reverse("website:privacy"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mailto:zephuyaa@gmail.com")
        self.assertContains(response, "Google User Messaging Platform")
        self.assertContains(response, "xóa tài khoản")
        self.assertNotContains(response, "<script")
        self.assertNotContains(response, "adsbygoogle.js")
        home = self.client.get(reverse("website:home"))
        self.assertContains(home, 'href="/chinh-sach-bao-mat/"')
        self.assertContains(home, "adsbygoogle.js")

    def test_account_deletion_has_public_request_path_and_no_ads(self):
        response = self.client.get(reverse("website:account_deletion"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GradeFlow – Chấm Trắc Nghiệm")
        self.assertContains(response, "mailto:zephuyaa@gmail.com?subject=")
        self.assertContains(response, "Không cần đăng nhập")
        self.assertContains(response, "Dữ liệu được xóa hoặc giữ lại")
        self.assertNotContains(response, "adsbygoogle.js")
        self.assertNotContains(response, "<script")
        self.assertContains(self.client.get(reverse("website:privacy")),
                            'href="/xoa-tai-khoan/"')

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.release = Path(temporary.name) / "stable.apk"
        self.apk_bytes = b"PK\x03\x04GradeFlow stable test APK\x00\xff"
        self.release.write_bytes(self.apk_bytes)
        self.enterContext(override_settings(GRADEFLOW_APK_PATH=self.release))

    def test_anonymous_public_pages_render_real_templates(self):
        for name, url, template in self.pages:
            with self.subTest(page=name):
                self.assertEqual(reverse(f"website:{name}"), url)
                self.assertEqual(resolve(url).view_name, f"website:{name}")
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)
                self.assertTemplateUsed(response, "website/base.html")
                self.assertFalse(response.wsgi_request.user.is_authenticated)
                self.assertEqual(response.context["active_page"], name)
                self.assertTrue(response.context["apk"]["available"])
                self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=()")

    def test_public_page_head_has_no_body(self):
        for _, url, _ in self.pages:
            with self.subTest(url=url):
                response = self.client.head(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b"")

    def test_public_routes_only_allow_get_and_head(self):
        urls = [url for _, url, _ in self.pages] + [
            reverse("website:apk_download"), reverse("chamtn_spa"),
        ]
        for url in urls:
            for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"):
                with self.subTest(url=url, method=method):
                    response = self.client.generic(method, url)
                    self.assertEqual(response.status_code, 405)
                    self.assertEqual(response.headers["Allow"], "GET, HEAD")
                    self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=()")

    def test_download_metadata_and_link(self):
        self.release.write_bytes(b"x" * 1_250_000)
        response = self.client.get(reverse("website:download"))
        self.assertEqual(response.context["apk"], {
            "available": True,
            "size_MB": 1.25,
            "sha256": "04DAA6933B66B99AA06934F0E9C6C673199C53331BB4914DAD942847E2D52032",
            "filename": "gradeflow-academic-ui-v1-2008-arm64.apk",
            "url": "/downloads/gradeflow.apk",
        })
        self.assertContains(response, 'href="/downloads/gradeflow.apk"')

    def test_apk_streams_exact_bytes_and_attachment_headers(self):
        self.assertEqual(reverse("website:apk_download"), "/downloads/gradeflow.apk")
        response = self.client.get(reverse("website:apk_download"))
        self.addCleanup(response.close)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/vnd.android.package-archive")
        self.assertEqual(response.headers["Content-Length"], str(len(self.apk_bytes)))
        self.assertEqual(response.headers["Content-Disposition"],
                         'attachment; filename="gradeflow-academic-ui-v1-2008-arm64.apk"')
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=()")
        self.assertEqual(b"".join(response.streaming_content), self.apk_bytes)

    def test_apk_head_preserves_headers_without_body(self):
        response = self.client.head(reverse("website:apk_download"))
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Length"], str(len(self.apk_bytes)))
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"")

    def test_missing_apk_get_and_head_return_404(self):
        self.release.unlink()
        for method in (self.client.get, self.client.head):
            with self.subTest(method=method.__name__):
                response = method(reverse("website:apk_download"))
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("Content-Disposition", response.headers)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=()")

    def test_missing_apk_is_disabled_on_page_and_download_is_404(self):
        self.release.unlink()
        response = self.client.get(reverse("website:download"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["apk"]["available"])
        self.assertIsNone(response.context["apk"]["size_MB"])
        self.assertIsNone(response.context["apk"]["url"])
        self.assertNotContains(response, 'href="/downloads/gradeflow.apk"')
        self.assertContains(response, "disabled")
        for method in (self.client.get, self.client.head):
            self.assertEqual(method(reverse("website:apk_download")).status_code, 404)

    def test_empty_or_directory_apk_is_unavailable(self):
        self.release.write_bytes(b"")
        for target in (self.release, self.release.parent / "directory.apk"):
            if target != self.release:
                target.mkdir()
            with self.subTest(target=target), override_settings(GRADEFLOW_APK_PATH=target):
                response = self.client.get(reverse("website:download"))
                self.assertFalse(response.context["apk"]["available"])
                self.assertEqual(self.client.get(reverse("website:apk_download")).status_code, 404)

    def test_unreadable_apk_is_unavailable(self):
        unreadable = Mock(wraps=self.release)
        unreadable.open.side_effect = PermissionError
        with patch("website.views._apk_path", return_value=unreadable):
            response = self.client.get(reverse("website:download"))
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context["apk"]["available"])
            self.assertEqual(self.client.get(reverse("website:apk_download")).status_code, 404)

    def test_file_removed_after_metadata_returns_404(self):
        response = self.client.get(reverse("website:download"))
        self.assertTrue(response.context["apk"]["available"])
        self.release.unlink()
        self.assertEqual(self.client.get(response.context["apk"]["url"]).status_code, 404)

    def test_default_path_uses_only_stable_release(self):
        release_dir = self.release.parent / "releases"
        release_dir.mkdir()
        stable = release_dir / "gradeflow-stable-arm64.apk"
        stable.write_bytes(self.apk_bytes)
        with override_settings(BASE_DIR=self.release.parent, GRADEFLOW_APK_PATH=None):
            response = self.client.get(reverse("website:apk_download"))
            self.assertEqual(b"".join(response.streaming_content), self.apk_bytes)
            response.close()
            stable.unlink()
            # An arbitrary neighboring APK must never become a fallback.
            self.assertEqual(self.client.get(reverse("website:apk_download")).status_code, 404)

    def test_query_parameters_cannot_select_download_path_or_filename(self):
        other = self.release.parent / "other.apk"
        other.write_bytes(b"not the public release")
        response = self.client.get(reverse("website:apk_download"), {
            "path": str(other), "filename": "other.apk", "file": "../../db.sqlite3",
        })
        self.addCleanup(response.close)
        self.assertEqual(b"".join(response.streaming_content), self.apk_bytes)
        self.assertIn(views.APK_FILENAME, response.headers["Content-Disposition"])

    def test_invalid_configured_paths_are_rejected(self):
        for target in ("relative.apk", "", 123, str(self.release.parent / "db.sqlite3")):
            with self.subTest(target=target), override_settings(GRADEFLOW_APK_PATH=target):
                with self.assertRaises(ImproperlyConfigured):
                    views.apk_download(RequestFactory().get("/downloads/gradeflow.apk"))

    def test_legacy_route_redirects_to_web_upload(self):
        for method in (self.client.get, self.client.head):
            response = method(reverse("chamtn_spa"))
            self.assertRedirects(response, reverse("grading:upload"), fetch_redirect_response=False)

    def test_existing_root_routes_still_resolve(self):
        routes = {
            "/dashboard/": "dashboard:index",
            "/dashboard/history/": "dashboard:history",
            "/grading/upload/": "grading:upload",
            "/grading/exams/": "grading:exams",
            "/accounts/login/": "accounts:login",
            "/accounts/profile/": "accounts:profile",
            "/api/v1/auth/login/": "api:login",
            "/admin/": "admin:index",
            "/offline/": "pwa_offline",
        }
        for url, name in routes.items():
            with self.subTest(url=url):
                self.assertEqual(resolve(url).view_name, name)
        self.assertEqual(resolve("/sw.js").func.__name__, "sw_view")
        with self.assertRaises(Resolver404):
            resolve("/downloads/other.apk")

    def test_app_pages_still_require_authentication(self):
        for name in ("dashboard:index", "dashboard:history", "grading:upload", "grading:exams"):
            url = reverse(name)
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}",
                                     fetch_redirect_response=False)


@override_settings(STORAGES=TEST_STORAGES)
class AuthenticatedAppTemplateTests(SimpleTestCase):
    def test_existing_app_templates_render_with_authenticated_context(self):
        user = get_user_model()(username="template-teacher", email="teacher@example.com",
                                first_name="Template", last_name="Teacher")
        pages = (
            ("dashboard:index", "dashboard/index.html"),
            ("dashboard:history", "dashboard/history.html"),
            ("grading:upload", "grading/upload.html"),
            ("grading:exams", "grading/exams.html"),
        )
        context = {
            "stats": {"total_exams": 0, "total_graded": 0, "today_graded": 0,
                      "avg_score": None, "pass_rate": None},
            "recent_exams": [], "recent_submissions": [], "submissions": [],
            "exams": [], "templates": [], "distribution_json": "{}",
            "selected_template": "", "selected_exam": None, "template_info": None,
        }
        for name, template in pages:
            with self.subTest(template=template):
                request = RequestFactory().get(reverse(name))
                request.user = user
                request.resolver_match = resolve(request.path)
                html = render_to_string(template, context, request=request)
                self.assertIn("teacher@example.com", html)
                self.assertIn(reverse("grading:upload"), html)
                self.assertNotIn("grading:live_camera", html)
                self.assertNotIn("getUserMedia", html)
