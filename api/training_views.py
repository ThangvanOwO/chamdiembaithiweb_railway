"""Admin question labelling: signed, expiring previews from unannotated photos."""
import base64
import hashlib
import json
import tempfile

from django.core import signing
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from grading.models import TrainingCorrection, TrainingSample
from grading.training_data import question_preview, validate_labels, labelled_answer, write_dataset


class TrainingAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_superuser)


def record_data(sample):
    return {'id': sample.pk, 'part': sample.part, 'question': sample.question,
            'subquestion': sample.subquestion, 'template_code': sample.template_code,
            'detected': sample.detected, 'answer': sample.answer, 'status': sample.status,
            'image_url': sample.image.url, 'cells': sample.cells, 'labels': sample.labels,
            'geometry': sample.geometry, 'revision': sample_revision(sample),
            'created_at': sample.created_at.isoformat()}


def sample_revision(sample):
    data = [sample.image.name, sample.cells, sample.labels, sample.geometry]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@api_view(['POST'])
@permission_classes([TrainingAdmin])
@parser_classes([MultiPartParser, FormParser])
def preview_api(request):
    image = request.FILES.get('image')
    if not image or image.size > 10 * 1024 * 1024:
        return Response({'error': 'Cần ảnh gốc nhỏ hơn 10 MB.'}, status=400)
    try:
        part, question = int(request.data.get('part', 0)), int(request.data.get('question', 0))
        corners = json.loads(request.data['corners']) if request.data.get('corners') else None
        data, png = question_preview(image.read(), request.data.get('template_code') or '40-08-06',
            part, question, request.data.get('subquestion', ''), corners)
        data['image_base64'] = base64.b64encode(png).decode('ascii')
        token = signing.dumps({'user': request.user.pk, 'data': data}, salt='training-preview-v1', compress=True)
        return Response({**data, 'preview_token': token})
    except (ValueError, TypeError, OverflowError) as exc:
        return Response({'error': str(exc)}, status=400)


@api_view(['POST'])
@permission_classes([TrainingAdmin])
def save_api(request):
    try:
        token = request.data.get('preview_token', '')
        if not isinstance(token, str) or len(token) > 1_000_000:
            raise ValueError('Bản xem trước không hợp lệ.')
        payload = signing.loads(token, salt='training-preview-v1', max_age=1800)
        if payload['user'] != request.user.pk:
            return Response({'error': 'Bản xem trước thuộc tài khoản khác.'}, status=403)
        if request.data.get('confirmed') is not True:
            raise ValueError('Hãy xác nhận vùng ảnh và nhãn trước khi lưu.')
        data, labels = payload['data'], request.data.get('labels')
        if data['geometry'].get('aligned') is not True:
            raise ValueError('Lưới vòng tròn chưa khớp ảnh. Quét Live lại trước khi lưu mẫu.')
        validate_labels(data['cells'], labels)
        answer = labelled_answer(data['part'], labels)
        # One source/question per contributor. A revision resets the review.
        with transaction.atomic():
            sample, created = TrainingCorrection.objects.get_or_create(
                teacher=request.user, source_hash=data['source_hash'], template_code=data['template_code'],
                part=data['part'], question=data['question'], subquestion=data['subquestion'])
            sample = TrainingCorrection.objects.select_for_update().get(pk=sample.pk)
            if not created and sample.labels == labels and sample.geometry == data['geometry']:
                return Response({'success': True, 'duplicate': True, **record_data(sample)})
            old_image = None
            if created or not sample.image or sample.geometry != data['geometry']:
                old_image = sample.image.name if sample.image else None
                sample.image.save(f'{sample.pk}.png', ContentFile(base64.b64decode(data['image_base64'])), save=False)
            sample.detected, sample.answer = data['detected'], answer
            sample.cells, sample.labels, sample.geometry = data['cells'], labels, data['geometry']
            sample.status, sample.reviewed_by, sample.reviewed_at = 'pending', None, None
            sample.save()
            if old_image and old_image != sample.image.name:
                storage = sample.image.storage
                transaction.on_commit(lambda: storage.delete(old_image))
        return Response({'success': True, **record_data(sample)}, status=201 if created else 200)
    except (signing.BadSignature, signing.SignatureExpired):
        return Response({'error': 'Bản xem trước hết hạn hoặc bị sửa. Mở lại câu để kiểm tra.'}, status=400)
    except (ValueError, TypeError, KeyError) as exc:
        return Response({'error': str(exc)}, status=400)


@api_view(['GET'])
@permission_classes([TrainingAdmin])
def list_api(request):
    samples = TrainingCorrection.objects.all()
    counts = {status: 0 for status in ('pending', 'approved', 'rejected')}
    counts.update({item['status']: item['count'] for item in samples.values('status').annotate(count=Count('id'))})
    status = request.query_params.get('status', 'pending')
    if status not in counts:
        return Response({'error': 'Trạng thái không hợp lệ.'}, status=400)
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except ValueError:
        return Response({'error': 'Số trang không hợp lệ.'}, status=400)
    filtered = samples.filter(status=status)
    return Response({'counts': counts, 'unverified': TrainingSample.objects.count(), 'count': filtered.count(),
                     'page': page, 'samples': [record_data(s) for s in filtered[(page-1)*20:page*20]]})


@api_view(['POST'])
@permission_classes([TrainingAdmin])
def review_api(request, sample_id):
    status = request.data.get('status')
    if status not in ('approved', 'rejected') or request.data.get('confirmed') is not True:
        return Response({'error': 'Xác nhận đã đối chiếu ảnh trước khi duyệt hoặc loại.'}, status=400)
    with transaction.atomic():
        sample = get_object_or_404(TrainingCorrection.objects.select_for_update(), pk=sample_id)
        if request.data.get('revision') != sample_revision(sample):
            return Response({'error': 'Mẫu đã thay đổi. Tải lại và đối chiếu nhãn mới trước khi duyệt.'}, status=409)
        try:
            validate_labels(sample.cells, sample.labels)
            if status == 'approved' and (sample.geometry.get('aligned') is not True or
                    not sample.image or not sample.image.storage.exists(sample.image.name)):
                raise ValueError('Ảnh chưa khớp lưới hoặc ảnh không tồn tại; không thể duyệt.')
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)
        sample.status, sample.reviewed_by, sample.reviewed_at = status, request.user, timezone.now()
        sample.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    return Response(record_data(sample))


@api_view(['GET'])
@permission_classes([TrainingAdmin])
def export_api(request):
    output = tempfile.TemporaryFile()
    try:
        write_dataset(output, TrainingCorrection.objects.all())
        output.seek(0)
        response = FileResponse(output, as_attachment=True, filename='gradeflow-reviewed-training.zip')
        response['Cache-Control'] = 'private, no-store'
        return response
    except Exception:
        output.close()
        raise
