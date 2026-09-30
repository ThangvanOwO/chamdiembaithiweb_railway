"""Web integration contracts; all tests prohibit database access.

Deployment contract: GRADEFLOW_APK_PATH may relocate the stable APK, but its
contents MUST match website.views.APK_SHA256 and APK_FILENAME. Verify that hash
when deploying or replacing the file. Request-time metadata intentionally uses
the fixed release checksum, not a digest of an arbitrary configured file.

Service-worker behavioral tests execute the actual served script using Node.js
with mocked browser/network/cache APIs. They skip explicitly if Node is absent.
"""

from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch
from urllib.parse import unquote, urljoin, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from grading import views as grading_views
from grading.models import Exam
from .tests import TEST_STORAGES


class Document(HTMLParser):
    """Inspect rendered HTML without depending on attribute order or whitespace."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.form_elements = []
        self.current_form = None
        self.links = []
        self.ids = set()
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current_form = attrs
        self.elements.append((tag, attrs))
        self.form_elements.append((self.current_form, tag, attrs))
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag in ("a", "area") and "href" in attrs:
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "form":
            self.current_form = None

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def element(self, tag, form_id=None, **attributes):
        matches = [attrs for form, name, attrs in self.form_elements
                   if (form_id is None or (form is not None and form.get("id") == form_id))
                   and name == tag and all(attrs.get(key) == value
                                          for key, value in attributes.items())]
        if len(matches) != 1:
            raise AssertionError(
                f"Expected one {tag} matching {attributes} in form {form_id!r}, got {matches}"
            )
        return matches[0]


class NoBrowserCameraMixin:
    def assert_no_browser_camera(self, html, document):
        for api in ("getUserMedia", "mediaDevices", "MediaRecorder", "getDisplayMedia"):
            self.assertNotIn(api, html)
        for tag, attrs in document.elements:
            self.assertNotEqual(tag, "video")
            if tag == "input":
                self.assertNotIn("capture", attrs)
        for href in document.links:
            self.assertNotIn(urlsplit(href).path, ("/chamtn/", "/grading/live-camera/"))


@override_settings(STORAGES=TEST_STORAGES)
class AuthenticatedInputContracts(NoBrowserCameraMixin, SimpleTestCase):
    def setUp(self):
        self.user = get_user_model()(username="contracts-teacher", email="teacher@example.com")

    def request(self, name, **query):
        request = RequestFactory().get(reverse(name), query)
        request.user = self.user
        request.resolver_match = resolve(request.path)
        return request

    def render_upload(self, template_code, exam=None):
        query = {"template": template_code}
        if exam is not None:
            query["exam_id"] = exam.pk
        request = self.request("grading:upload", **query)
        with patch.object(grading_views.Exam.objects, "filter", return_value=[]) as exams, \
                patch.object(grading_views.Submission.objects, "filter", return_value=[]) as submissions, \
                patch.object(grading_views.Exam.objects, "get", return_value=exam) as selected:
            response = grading_views.upload_view(request)
        exams.assert_called_once_with(teacher=self.user)
        submissions.assert_called_once_with(teacher=self.user)
        if exam is not None:
            selected.assert_called_once_with(id=str(exam.pk), teacher=self.user)
        else:
            selected.assert_not_called()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        document = Document(html)
        self.assert_no_browser_camera(html, document)
        form = document.element("form", id="upload-form")
        self.assertEqual(form["method"].lower(), "post")
        self.assertEqual(form["enctype"], "multipart/form-data")
        target = urlsplit(urljoin(request.path, form.get("action", ""))).path
        self.assertEqual(resolve(target).view_name, "grading:upload")
        self.assertEqual(document.element("input", form_id="upload-form", name="template_code")["value"], template_code)
        self.assertTrue(document.element("input", form_id="upload-form", name="csrfmiddlewaretoken")["value"])
        images = document.element("input", form_id="upload-form", name="images")
        self.assertEqual(images["type"], "file")
        self.assertEqual(images["accept"], "image/*")
        self.assertIn("multiple", images)
        self.assertIn(reverse("website:download"), document.links)
        self.assertIn(reverse("website:guide"), document.links)
        return html, document

    def test_selected_template_upload_renders_file_submission_branch(self):
        template = grading_views.EXAM_TEMPLATES[0]
        html, _ = self.render_upload(template["code"])
        self.assertIn(template["label"], html)

    def test_unknown_selected_template_renders_without_template_info(self):
        self.render_upload("unknown-template")

    def test_selected_exam_upload_preserves_exam_and_answer_key_fields(self):
        template = grading_views.EXAM_TEMPLATES[0]
        answer_key = '{"parts": [24, 6, 0], "label": "A & B"}'
        exam = Exam(pk=42, teacher=self.user, title="Contract exam", num_questions=30,
                    template_code=template["code"], answer_key=answer_key)
        html, document = self.render_upload(template["code"], exam)
        self.assertIn(exam.title, html)
        self.assertEqual(document.element("input", form_id="upload-form", name="exam_id")["value"], "42")
        self.assertEqual(document.element("input", form_id="upload-form", name="answer_key")["value"], answer_key)

    def test_exam_import_preserves_inputs_and_parse_api_contracts(self):
        request = self.request("grading:exam_import")
        response = grading_views.exam_import_view(request)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        document = Document(html)
        self.assert_no_browser_camera(html, document)
        upload = document.element("input", type="file")
        self.assertEqual(set(upload["accept"].split(",")),
                         {".xlsx", ".jpg", ".jpeg", ".png", ".bmp", ".webp"})
        form = document.element("form", id="import-form")
        self.assertEqual(form["method"].lower(), "post")
        target = urlsplit(urljoin(request.path, form.get("action", ""))).path
        self.assertEqual(resolve(target).view_name, "grading:exam_import")
        for field in ("title", "subject", "num_questions", "config_json", "template_code", "variants_json"):
            self.assertEqual(document.element("input", form_id="import-form", name=field)["type"], "hidden")
        self.assertTrue(document.element("input", form_id="import-form", name="csrfmiddlewaretoken")["value"])
        for path, name in (("/grading/api/parse-image/", "grading:parse_image"),
                           ("/grading/api/parse-excel/", "grading:parse_excel")):
            self.assertEqual(reverse(name), path)
            self.assertEqual(resolve(path).view_name, name)
            self.assertIn(path, html)
        self.assertRegex(html, r"formData\.append\(['\"]file['\"],\s*file\)")
        self.assertRegex(html, r"fetch\(apiUrl,\s*\{\s*method:\s*['\"]POST['\"]")
        self.assertIn("'X-CSRFToken': csrfToken", html)
        self.assertIn("window.__examTemplates = " + json.dumps(grading_views.EXAM_TEMPLATES), html)


@override_settings(STORAGES=TEST_STORAGES)
class PublicLinkContracts(NoBrowserCameraMixin, SimpleTestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.release = Path(temporary.name) / "stable.apk"
        self.enterContext(override_settings(GRADEFLOW_APK_PATH=self.release))

    def check_public_links(self):
        for user in (AnonymousUser(), get_user_model()(username="public-teacher")):
            documents = {}
            for name in ("home", "guide", "download"):
                path = reverse(f"website:{name}")
                request = RequestFactory().get(path)
                request.user = user
                request.resolver_match = resolve(path)
                response = request.resolver_match.func(request)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                documents[path] = Document(html)
                self.assert_no_browser_camera(html, documents[path])
            for path, document in documents.items():
                self.assertTrue(document.links, f"No links checked for {path}")
                for href in document.links:
                    with self.subTest(page=path, href=href, authenticated=user.is_authenticated):
                        self.assertTrue(href, "Empty link target")
                        target = urlsplit(urljoin("http://testserver" + path, href))
                        self.assertIn(target.scheme, ("http", "https", "mailto", "tel"))
                        if target.netloc != "testserver":
                            continue
                        destination = unquote(target.path)
                        resolve(destination)
                        if target.fragment and destination in documents:
                            self.assertIn(unquote(target.fragment), documents[destination].ids)
                        if destination == reverse("website:apk_download"):
                            self.assertTrue(self.release.is_file(), "Link to unavailable APK")

    def test_all_public_navigation_links_and_fragments_resolve(self):
        self.release.write_bytes(b"PK\x03\x04contract fixture")
        self.check_public_links()

    def test_missing_apk_public_navigation_links_and_fragments_resolve(self):
        self.check_public_links()


NODE = shutil.which("node")

# Execute the served worker unchanged. Only browser facilities are substituted;
# the harness does not copy or reimplement its routing/cache policy.
WORKER_HARNESS = r"""
const vm = require('node:vm');
const fs = require('node:fs');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const listeners = {};
let options = {}, log = {};
function reset() {
  log = {reads: [], writes: [], adds: [], deleted: [], network: [], opened: []};
}
function response(body, status = 200) {
  return {body, status, ok: status >= 200 && status < 300,
          clone() { return response(body, status); }};
}
const pathOf = request => new URL(typeof request === 'string' ? request : request.url,
                                 'https://gradeflow.test').pathname;
const context = {
  URL,
  Response: class { constructor(body, init) { Object.assign(this, response(body, init.status)); } },
  self: {
    location: {origin: 'https://gradeflow.test'},
    addEventListener(name, callback) { listeners[name] = callback; },
    skipWaiting() { log.skipWaiting = true; },
    clients: {claim() { log.claimed = true; }}
  },
  caches: {
    async keys() { return ['gradeflow-static-v1', 'gradeflow-dynamic-v1',
                           'gradeflow-static-v2', 'unrelated-cache']; },
    async delete(key) { log.deleted.push(key); return true; },
    async open(key) {
      log.opened.push(key);
      return {
        async add(path) { log.adds.push(path); },
        async put(request) { log.writes.push(pathOf(request)); }
      };
    },
    async match(request) {
      const path = pathOf(request);
      log.reads.push(path);
      if (path === '/offline/') return options.offlineCached ? response('offline') : undefined;
      return options.cacheHit ? response('cached') : undefined;
    }
  },
  async fetch(request) {
    log.network.push(pathOf(request));
    if (options.networkOffline) throw new Error('offline');
    return response('network', options.networkStatus || 200);
  }
};
vm.runInNewContext(payload.source, context, {timeout: 1000});
(async () => {
  if (payload.action === 'lifecycle') {
    reset();
    for (const name of ['install', 'activate']) {
      const pending = [];
      listeners[name]({waitUntil(value) { pending.push(value); }});
      await Promise.all(pending);
    }
    process.stdout.write(JSON.stringify(log));
    return;
  }
  const results = [];
  for (options of payload.requests) {
    reset();
    const pending = [];
    let result;
    listeners.fetch({
      request: {url: new URL(options.path, 'https://gradeflow.test').href,
                method: options.method || 'GET', mode: options.mode || 'navigate'},
      waitUntil(value) { pending.push(value); },
      respondWith(value) { result = value; }
    });
    const resolved = await result;
    await Promise.all(pending);
    results.push({...log, intercepted: result !== undefined,
                  body: resolved?.body, status: resolved?.status});
  }
  process.stdout.write(JSON.stringify(results));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


@skipUnless(NODE, "Node.js is required to execute service-worker policy tests")
class ServiceWorkerContracts(SimpleTestCase):
    def run_worker(self, requests=None, action="fetch"):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("application/javascript"))
        completed = subprocess.run(
            [NODE, "-e", WORKER_HARNESS],
            input=json.dumps({"source": response.content.decode(), "action": action,
                              "requests": requests or []}),
            text=True, encoding="utf-8", capture_output=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_install_and_activation_retire_old_gradeflow_caches(self):
        result = self.run_worker(action="lifecycle")
        self.assertEqual(result["adds"], ["/offline/"])
        self.assertEqual(result["opened"], ["gradeflow-static-v2"])
        self.assertCountEqual(result["deleted"], ["gradeflow-static-v1", "gradeflow-dynamic-v1"])
        self.assertTrue(result["skipWaiting"])
        self.assertTrue(result["claimed"])

    def test_downloads_media_api_external_and_non_get_requests_bypass_worker(self):
        requests = [{"path": path, "networkOffline": True, "cacheHit": True}
                    for path in ("/downloads/gradeflow.apk", "/media/private.jpg",
                                 "/api/v1/exams/", "/grading/api/parse-image/",
                                 "/grading/api/parse-excel/", "https://other.test/static/app.js")]
        requests += [{"path": "/static/app.js", "method": method}
                     for method in ("HEAD", "POST", "PUT", "PATCH", "DELETE")]
        for request, result in zip(requests, self.run_worker(requests)):
            with self.subTest(request=request):
                self.assertFalse(result["intercepted"])
                for operation in ("reads", "writes", "network", "opened"):
                    self.assertEqual(result[operation], [])

    def test_navigation_is_network_first_without_caching_html(self):
        paths = ("/", "/huong-dan/", "/tai-ung-dung/", "/dashboard/",
                 "/accounts/login/", "/grading/upload/", "/grading/exams/import/")
        requests = [{"path": path, "cacheHit": True} for path in paths]
        for path, result in zip(paths, self.run_worker(requests)):
            with self.subTest(path=path):
                self.assertTrue(result["intercepted"])
                self.assertEqual(result["body"], "network")
                self.assertEqual(result["network"], [path])
                self.assertEqual(result["reads"], [])
                self.assertEqual(result["writes"], [])

    def test_offline_navigation_uses_offline_page_or_503(self):
        results = self.run_worker([
            {"path": "/grading/upload/", "networkOffline": True, "offlineCached": cached,
             "cacheHit": True} for cached in (True, False)
        ])
        self.assertEqual(results[0]["body"], "offline")
        self.assertEqual(results[0]["status"], 200)
        self.assertEqual(results[1]["status"], 503)
        for result in results:
            self.assertEqual(result["reads"], ["/offline/"])
            self.assertEqual(result["writes"], [])

    def test_static_assets_use_cache_and_only_cache_successful_network_responses(self):
        path = "/static/css/website.css"
        hit, miss, error = self.run_worker([
            {"path": path, "mode": "cors", "cacheHit": True},
            {"path": path, "mode": "cors"},
            {"path": path, "mode": "cors", "networkStatus": 404},
        ])
        self.assertEqual(hit["body"], "cached")
        self.assertEqual(hit["network"], [])
        self.assertEqual(hit["writes"], [])
        self.assertEqual(miss["body"], "network")
        self.assertEqual(miss["writes"], [path])
        self.assertEqual(miss["opened"], ["gradeflow-static-v2"])
        self.assertEqual(error["status"], 404)
        self.assertEqual(error["writes"], [])
