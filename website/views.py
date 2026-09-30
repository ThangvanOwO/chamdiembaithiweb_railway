"""Public pages and the single, server-configured stable Android release."""

import os
from functools import wraps
from pathlib import Path
import stat

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import FileResponse, Http404, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_safe


APK_FILENAME = "gradeflow-academic-ui-v1-2008-arm64.apk"
# Release metadata supplied at deployment; never hash the APK on a request.
APK_SHA256 = "04DAA6933B66B99AA06934F0E9C6C673199C53331BB4914DAD942847E2D52032"
APK_CONTENT_TYPE = "application/vnd.android.package-archive"


def public_response(view):
    """Keep camera and microphone disabled, including on 404/405 responses."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except Http404:
            response = HttpResponseNotFound("The Android download is currently unavailable.")
        response["Permissions-Policy"] = "camera=(), microphone=()"
        response["X-Content-Type-Options"] = "nosniff"
        if "Cache-Control" not in response:
            response["Cache-Control"] = "no-store"
        return response
    return wrapped


def _apk_path():
    """Only deployment configuration can select the file, never request data."""
    configured = getattr(settings, "GRADEFLOW_APK_PATH", None)
    if configured is None:
        return Path(settings.BASE_DIR) / "releases" / "gradeflow-stable-arm64.apk"
    try:
        path = Path(configured)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured("GRADEFLOW_APK_PATH must be an absolute APK path.") from exc
    if not path.is_absolute() or path.suffix.lower() != ".apk" or "\x00" in str(path):
        raise ImproperlyConfigured("GRADEFLOW_APK_PATH must be an absolute APK path.")
    return path


def _open_apk():
    path = _apk_path()
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise Http404("The Android download is currently unavailable.")
        apk_file = path.open("rb")
    except OSError as exc:
        raise Http404("The Android download is currently unavailable.") from exc
    try:
        info = os.fstat(apk_file.fileno())
    except OSError as exc:
        apk_file.close()
        raise Http404("The Android download is currently unavailable.") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
        apk_file.close()
        raise Http404("The Android download is currently unavailable.")
    return apk_file, info.st_size


def _page_context(active_page):
    apk = {
        "available": False,
        "size_MB": None,
        "sha256": APK_SHA256,
        "filename": APK_FILENAME,
        "url": None,
    }
    try:
        apk_file, size = _open_apk()
    except Http404:
        pass
    else:
        apk_file.close()
        apk.update(
            available=True,
            size_MB=round(size / 1_000_000, 2),
            url=reverse("website:apk_download"),
        )
    return {"active_page": active_page, "apk": apk}


@public_response
@require_safe
def home(request):
    return render(request, "website/home.html", _page_context("home"))


@public_response
@require_safe
def guide(request):
    return render(request, "website/guide.html", _page_context("guide"))


@public_response
@require_safe
def privacy(request):
    return render(request, "website/privacy.html", _page_context("privacy"))


@public_response
@require_safe
def account_deletion(request):
    response = render(request, "website/account_deletion.html", _page_context("account_deletion"))
    # Cloudflare must leave the contact address visible to users and Play's crawler.
    response["Cache-Control"] = "no-store, no-transform"
    return response


@public_response
@require_safe
def download(request):
    return render(request, "website/download.html", _page_context("download"))


@public_response
@require_safe
def apk_download(request):
    apk_file, _ = _open_apk()
    response = FileResponse(
        apk_file, as_attachment=True, filename=APK_FILENAME,
        content_type=APK_CONTENT_TYPE,
    )
    return response


@public_response
@require_safe
def legacy_upload(request):
    return redirect("grading:upload")
