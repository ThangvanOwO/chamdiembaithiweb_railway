"""Billing boundary shared by the web, mobile and legacy batch scanners."""
import hashlib
import json
import re
import zipfile
from functools import wraps

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from rest_framework.renderers import JSONRenderer

from .credits import CreditError, InsufficientCredits, finish_scan, reserve_scan


def _request_identity(request, kwargs):
    data = request.data if hasattr(request, 'data') else request.POST
    digest = hashlib.sha256(request.get_full_path().encode())
    params = {k: data.getlist(k) if hasattr(data, 'getlist') else data[k]
              for k in sorted(data) if k not in request.FILES and k not in ('csrfmiddlewaretoken', 'scan_key')}
    digest.update(json.dumps(params, sort_keys=True, default=str).encode())
    # A new answer key must not replay a result produced with the old key.
    from grading.models import Exam, Submission
    exam_id = data.get('exam_id') or request.GET.get('exam_id') or kwargs.get('exam_id')
    if kwargs.get('submission_id'):
        sub = Submission.objects.filter(pk=kwargs['submission_id'], teacher=request.user).first()
        if sub:
            exam_id = sub.exam_id
            digest.update(str((sub.image.name, sub.template_code, sub.variant_id)).encode())
    if exam_id:
        try:
            exam = Exam.objects.filter(pk=exam_id, teacher=request.user).first()
        except (ValueError, TypeError):
            exam = None  # The view remains responsible for input validation.
        if exam:
            digest.update(str((exam.answer_key, exam.template_code)).encode())
            digest.update(json.dumps(list(exam.variants.order_by('pk').values_list('variant_code', 'answers_json'))).encode())
    for field in sorted(request.FILES):
        for upload in request.FILES.getlist(field):
            digest.update(f'{field}:{upload.size}:'.encode())
            for chunk in upload.chunks():
                digest.update(chunk)
            upload.seek(0)
    fingerprint = digest.hexdigest()
    key = request.headers.get('Idempotency-Key') or data.get('scan_key') or fingerprint
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,128}', key):
        raise CreditError('Mã yêu cầu không hợp lệ.')
    return key, fingerprint


def _scan_count(request, mode):
    if mode == 'regrade':
        return 1
    if mode == 'upload':
        return len(request.FILES.getlist('images'))
    if mode == 'batch':
        count = 0
        for upload in request.FILES.getlist('files') or request.FILES.getlist('file'):
            if upload.name.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(upload) as archive:
                        count += sum(1 for item in archive.infolist() if not item.is_dir()
                                     and item.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')))
                except zipfile.BadZipFile:
                    pass  # The existing view reports invalid archives.
                finally:
                    upload.seek(0)
            else:
                count += 1
        return count
    return int(bool(request.FILES.get('image') or request.POST.get('image_base64')))


def bill_scans(mode='single', web=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != 'POST':
                return view(request, *args, **kwargs)
            if not request.user.is_authenticated or not request.user.is_active:
                return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập.'}, status=401)
            count = _scan_count(request, mode)
            if not count:
                return view(request, *args, **kwargs)
            try:
                key, fingerprint = _request_identity(request, kwargs)
                operation, created = reserve_scan(request.user, key, fingerprint, count)
                if not created:
                    if not operation.finished:
                        raise CreditError('Yêu cầu này đang được xử lý. Vui lòng đợi rồi thử lại cùng mã yêu cầu.')
                    response = HttpResponse(operation.response_body, status=operation.response_status,
                                            content_type=operation.response_type)
                    if operation.redirect_url:
                        response['Location'] = operation.redirect_url
                    response['Idempotency-Replayed'] = 'true'
                    return response
            except CreditError as exc:
                if web:
                    messages.error(request, str(exc))
                    return redirect('accounts:credits')
                return JsonResponse({'success': False, 'error': str(exc), 'credits_url': '/accounts/credits/'},
                                    status=402 if isinstance(exc, InsufficientCredits) else 409)
            request.billable_scans = 0
            try:
                response = view(request, *args, **kwargs)
                if hasattr(response, 'data'):
                    body = JSONRenderer().render(response.data).decode('utf-8')
                    content_type = 'application/json'
                else:
                    body = response.content.decode(response.charset)
                    content_type = response.get('Content-Type', 'text/html')
                finish_scan(operation, request.billable_scans, body, response.status_code,
                            content_type, response.get('Location', ''))
                response['Idempotency-Key'] = key
                return response
            except Exception:
                # Unhandled failures after completed items retain only those items' cost.
                finish_scan(operation, request.billable_scans,
                            json.dumps({'success': False, 'error': 'Xử lý bị gián đoạn. Vui lòng kiểm tra danh sách bài đã chấm.'}),
                            500, 'application/json')
                raise
        return wrapped
    return decorate
