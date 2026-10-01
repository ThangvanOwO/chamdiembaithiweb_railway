"""Serve uploaded images only after checking the database owner."""
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.decorators import api_view

from accounts.models import TeacherProfile
from grading.models import Submission, TrainingSample, TrainingCorrection


IMAGE_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
               '.webp': 'image/webp', '.bmp': 'image/bmp', '.tif': 'image/tiff',
               '.tiff': 'image/tiff'}
DERIVATIVES = ('_result', '_overlay', '_name', '_calibration', '_gray', '_thresh', '_detect')


@api_view(['GET', 'HEAD'])
def private_media(request, path):
    relative = PurePosixPath(path)
    if '\\' in path or relative.is_absolute() or '..' in relative.parts:
        raise Http404
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or target.suffix.lower() not in IMAGE_TYPES:
        raise Http404

    owner_id = None
    if path.startswith('submissions/'):
        record = Submission.objects.filter(image=path).values('teacher_id').first()
        if not record and relative.suffix == '.jpg':
            for suffix in DERIVATIVES:
                if relative.stem.endswith(suffix):
                    stem = str(relative.with_name(relative.stem[:-len(suffix)]))
                    candidates = [stem + extension for extension in IMAGE_TYPES]
                    candidates += [stem + extension.upper() for extension in IMAGE_TYPES]
                    record = Submission.objects.filter(image__in=candidates).values('teacher_id').first()
                    break
        owner_id = record['teacher_id'] if record else None
    elif path.startswith('training/'):
        owner_id = TrainingSample.objects.filter(image=path).values_list('teacher_id', flat=True).first()
    elif path.startswith('training_corrections/'):
        owner_id = TrainingCorrection.objects.filter(image=path).values_list('teacher_id', flat=True).first()
        if owner_id is None and path.startswith('training_corrections/sources/'):
            owner_id = TrainingCorrection.objects.filter(geometry__source_image=path).values_list('teacher_id', flat=True).first()
    elif path.startswith('avatars/'):
        owner_id = TeacherProfile.objects.filter(avatar=path).values_list('user_id', flat=True).first()

    if owner_id is None or (owner_id != request.user.pk and not request.user.is_superuser):
        raise Http404
    try:
        response = FileResponse(target.open('rb'), content_type=IMAGE_TYPES[target.suffix.lower()])
    except (FileNotFoundError, IsADirectoryError):
        raise Http404
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['Vary'] = 'Cookie, Authorization'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response
