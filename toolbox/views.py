import io
import json
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from api.notification_views import NotificationAdmin
from grading.models import Exam, Submission
from grading.views import EXAM_TEMPLATES
from .importing import read_table, preview_rows, IMPORT_SALT
from .models import Classroom, Student, ExamRosterEntry, SubmissionReview, SupportTicket
from .reports import report_data, recognition_issues, review_of, csv_report, xlsx_report, pdf_report
from .serializers import ClassroomInput, StudentInput, TicketInput


def owned_class(request, pk):
    return get_object_or_404(Classroom, pk=pk, owner=request.user)


def owned_exam(request, pk):
    return get_object_or_404(Exam, pk=pk, teacher=request.user)


def positive_int(raw, name, default=None):
    try:
        value = int(raw) if raw not in (None, '') else default
        if value is not None and value < 1:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise ValidationError({name: 'Nhập một số nguyên dương.'})


def class_json(item):
    total = getattr(item, 'student_count', None)
    return {'id': item.pk, 'name': item.name, 'school_year': item.school_year, 'archived': item.archived,
            'student_count': total if total is not None else item.students.filter(archived=False).count()}


def student_json(item):
    return {'id': item.pk, 'name': item.name, 'student_id': item.student_id, 'archived': item.archived}


@api_view(['GET', 'POST'])
def classrooms(request):
    if request.method == 'POST':
        form = ClassroomInput(data=request.data)
        form.is_valid(raise_exception=True)
        return Response(class_json(form.save(owner=request.user)), status=201)
    query = Classroom.objects.filter(owner=request.user, archived=request.query_params.get('archived') == '1')
    query = query.annotate(student_count=Count('students', filter=Q(students__archived=False)))
    return Response({'items': [class_json(c) for c in query]})


@api_view(['GET', 'PATCH', 'DELETE'])
def classroom_detail(request, classroom_id):
    item = owned_class(request, classroom_id)
    if request.method == 'DELETE':
        item.archived = True
        item.save(update_fields=['archived'])
        return Response({'ok': True})
    if request.method == 'PATCH':
        form = ClassroomInput(item, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        item = form.save()
    return Response({**class_json(item), 'students': [student_json(s) for s in item.students.filter(archived=False)]})


@api_view(['POST'])
def students(request, classroom_id):
    item = owned_class(request, classroom_id)
    if item.archived:
        raise ValidationError('Khôi phục lớp trước khi thêm học sinh.')
    form = StudentInput(data=request.data)
    form.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            student = form.save(classroom=item)
    except IntegrityError:
        raise ValidationError({'student_id': 'Số báo danh đã tồn tại trong lớp.'})
    return Response(student_json(student), status=201)


@api_view(['PATCH', 'DELETE'])
def student_detail(request, student_id):
    student = get_object_or_404(Student, pk=student_id, classroom__owner=request.user)
    if request.method == 'DELETE':
        student.archived = True
        student.save(update_fields=['archived'])
        return Response({'ok': True})
    form = StudentInput(student, data=request.data, partial=True)
    form.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            form.save()
    except IntegrityError:
        raise ValidationError({'student_id': 'Số báo danh đã tồn tại trong lớp.'})
    return Response(student_json(student))


def signed_import(request, token, salt, classroom):
    try:
        data = signing.loads(token, salt=salt, max_age=1800)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('Bản xem trước đã hết hạn hoặc không hợp lệ. Chọn lại file.')
    if data.get('owner') != request.user.pk or data.get('classroom') != classroom.pk:
        raise ValidationError('Bản xem trước không thuộc lớp/tài khoản này.')
    return data


@api_view(['POST'])
def import_preview(request, classroom_id):
    classroom = owned_class(request, classroom_id)
    if classroom.archived:
        raise ValidationError('Khôi phục lớp trước khi nhập danh sách.')
    if 'file' in request.FILES:
        headers, values = read_table(request.FILES['file'])
        normalized = [''.join(c for c in unicodedata.normalize('NFD', h.lower().replace('đ', 'd'))
                              if unicodedata.category(c) != 'Mn').replace(' ', '') for h in headers]
        def suggest(aliases):
            return next((i for i, name in enumerate(normalized) if name in aliases), -1)
        token = signing.dumps({'owner': request.user.pk, 'classroom': classroom.pk, 'headers': headers, 'values': values},
                              salt=IMPORT_SALT + '.source', compress=True)
        return Response({'headers': headers, 'sample': values[:5], 'count': len(values), 'source_token': token,
                         'name_column': suggest({'hoten', 'hovaten', 'name', 'fullname'}),
                         'id_column': suggest({'sbd', 'sobaodanh', 'student_id', 'studentid'})})
    source = signed_import(request, request.data.get('source_token'), IMPORT_SALT + '.source', classroom)
    try:
        name_column, id_column = int(request.data['name_column']), int(request.data['id_column'])
    except (KeyError, ValueError, TypeError):
        raise ValidationError('Chọn cột họ tên và số báo danh.')
    return Response(preview_rows(classroom, source['headers'], source['values'], name_column, id_column))


@api_view(['POST'])
def import_confirm(request, classroom_id):
    classroom = owned_class(request, classroom_id)
    data = signed_import(request, request.data.get('confirmation'), IMPORT_SALT, classroom)
    if classroom.archived:
        raise ValidationError('Khôi phục lớp trước khi nhập danh sách.')
    added, existing = 0, 0
    try:
        with transaction.atomic():
            Classroom.objects.select_for_update().get(pk=classroom.pk)
            for row in data['rows']:
                student, created = Student.objects.get_or_create(classroom=classroom, student_id=row['student_id'],
                                                                 defaults={'name': row['name']})
                if student.name != row['name']:
                    raise ValidationError('Danh sách lớp đã thay đổi. Xem trước lại file để tránh trùng SBD.')
                if student.archived:
                    student.archived = False
                    student.save(update_fields=['archived'])
                added += int(created)
                existing += int(not created)
    except IntegrityError:
        raise ValidationError('Danh sách lớp đang được thay đổi. Xem trước lại file.')
    return Response({'ok': True, 'added': added, 'existing': existing})


@api_view(['GET', 'POST'])
def exam_roster(request, exam_id):
    exam = owned_exam(request, exam_id)
    if request.method == 'POST':
        field = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=100)
        ids = set(field.run_validation(request.data.get('classroom_ids')))
        classes = list(Classroom.objects.filter(owner=request.user, archived=False, pk__in=ids))
        if len(classes) != len(ids):
            raise ValidationError('Có lớp không tồn tại hoặc không thuộc tài khoản.')
        try:
            with transaction.atomic():
                Exam.objects.select_for_update().get(pk=exam.pk)
                existing = {r.student_id: r for r in ExamRosterEntry.objects.filter(exam=exam)}
                for classroom in classes:
                    for student in classroom.students.filter(archived=False):
                        previous = existing.get(student.student_id)
                        if previous:
                            if previous.source_student_id != student.pk:
                                raise ValidationError(f'SBD {student.student_id} trùng giữa các lớp. Điều chỉnh trước khi gắn đề.')
                            if not previous.active:
                                previous.active = True
                                previous.save(update_fields=['active'])
                            continue
                        entry = ExamRosterEntry.objects.create(exam=exam, source_student=student, classroom=classroom,
                                                               student_id=student.student_id, student_name=student.name,
                                                               class_name=classroom.name)
                        existing[entry.student_id] = entry
        except IntegrityError:
            raise ValidationError('Số báo danh trùng trong danh sách dự thi.')
    return Response(report_data(exam))


@api_view(['POST'])
def review_submission(request, submission_id):
    sub = get_object_or_404(Submission, pk=submission_id, teacher=request.user)
    with transaction.atomic():
        review, _ = SubmissionReview.objects.select_for_update().get_or_create(submission=sub)
        if 'roster_id' in request.data:
            roster_id = request.data['roster_id']
            review.roster_entry = get_object_or_404(ExamRosterEntry, pk=roster_id, exam_id=sub.exam_id,
                                                   exam__teacher=request.user, active=True) if roster_id is not None else None
        if 'reviewed' in request.data:
            reviewed = serializers.BooleanField().run_validation(request.data['reviewed'])
            review.reviewed_at = timezone.now() if reviewed else None
        if request.data.get('representative') is not None:
            selected = serializers.BooleanField().run_validation(request.data['representative'])
            if selected and (sub.status != 'completed' or sub.score is None):
                raise ValidationError('Chỉ chọn bài đã chấm có điểm làm bài đại diện.')
            if selected:
                Exam.objects.select_for_update().get(pk=sub.exam_id, teacher=request.user)
                roster = review.roster_entry or ExamRosterEntry.objects.filter(exam_id=sub.exam_id, active=True,
                                                                             student_id=sub.student_id.strip()).first()
                if roster:
                    SubmissionReview.objects.filter(Q(roster_entry=roster) | Q(submission__exam_id=sub.exam_id,
                                                                               submission__student_id=roster.student_id)).update(representative=False)
                    review.roster_entry = roster
                else:
                    SubmissionReview.objects.filter(submission__exam_id=sub.exam_id, submission__student_id=sub.student_id).update(representative=False)
            review.representative = selected
        review.save()
    return Response({'ok': True, 'reviewed': bool(review.reviewed_at), 'roster_id': review.roster_entry_id,
                     'representative': review.representative})


@api_view(['GET'])
def report(request, exam_id):
    exam = owned_exam(request, exam_id)
    classroom_id = positive_int(request.query_params.get('classroom_id'), 'classroom_id')
    if classroom_id:
        owned_class(request, classroom_id)
    return Response(report_data(exam, classroom_id))


@api_view(['GET'])
def export_report(request, exam_id, file_format):
    exam = owned_exam(request, exam_id)
    classroom_id = positive_int(request.query_params.get('classroom_id'), 'classroom_id')
    if classroom_id:
        owned_class(request, classroom_id)
    data = report_data(exam, classroom_id)
    formats = {'csv': (csv_report, 'text/csv; charset=utf-8'),
               'xlsx': (xlsx_report, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
               'pdf': (pdf_report, 'application/pdf')}
    if file_format not in formats:
        raise ValidationError('Định dạng không được hỗ trợ.')
    generator, content_type = formats[file_format]
    response = HttpResponse(generator(data), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="GradeFlow_{exam.pk}.{file_format}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['GET'])
def review_queue(request):
    exam_id = positive_int(request.query_params.get('exam_id'), 'exam_id')
    if exam_id:
        owned_exam(request, exam_id)
    exams = Exam.objects.filter(teacher=request.user)
    if exam_id:
        exams = exams.filter(pk=exam_id)
    items = []
    for exam in exams:
        data = report_data(exam)
        # Include every duplicate, not only the representative shown in a gradebook.
        issues_by_id = {}
        for row in data['rows']:
            for pk in row['candidates']:
                issues_by_id[pk] = [issue for issue in row['issues'] if issue == 'Chưa ghép học sinh' or 'phiếu cùng số báo danh' in issue]
        for sub in Submission.objects.filter(exam=exam, teacher=request.user).select_related('toolbox_review'):
            issues = list(dict.fromkeys(recognition_issues(sub) + issues_by_id.get(sub.pk, [])))
            if issues:
                review = review_of(sub)
                items.append({'id': sub.pk, 'exam_id': exam.pk, 'exam_title': exam.title, 'student_id': sub.student_id,
                              'score': sub.score_10, 'issues': issues, 'reviewed': bool(review and review.reviewed_at),
                              'roster_id': review.roster_entry_id if review else None,
                              'representative': bool(review and review.representative)})
    page = positive_int(request.query_params.get('page'), 'page', 1)
    start = (page - 1) * 50
    return Response({'items': items[start:start + 50], 'count': len(items), 'page': page, 'has_more': start + 50 < len(items)})


@api_view(['GET'])
def template_pdf(request, code):
    template = next((t for t in EXAM_TEMPLATES if t['code'] == code), None)
    if not template:
        return Response({'message': 'Không tìm thấy mẫu phiếu.'}, status=404)
    root = Path(settings.BASE_DIR) / 'cacmaubaithi'
    folder = (root / template['folder']).resolve()
    if not folder.is_relative_to(root.resolve()) or not folder.is_dir():
        return Response({'message': 'Mẫu chưa có file để in.'}, status=404)
    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png'))
    if not images:
        return Response({'message': 'Mẫu chưa có file để in.'}, status=404)
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    pdf.setTitle(f'GradeFlow · Mẫu {code}')
    for image in images:
        pdf.drawImage(ImageReader(str(image)), 0, 0, width=A4[0], height=A4[1], preserveAspectRatio=True, anchor='c')
        pdf.showPage()
    pdf.save()
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="GradeFlow_mau_{code}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


def ticket_json(ticket):
    return {'id': ticket.pk, 'owner': ticket.owner.get_username(), 'message': ticket.message, 'technical': ticket.technical,
            'status': ticket.status, 'admin_note': ticket.admin_note, 'created_at': ticket.created_at,
            'has_image': bool(ticket.image)}


@api_view(['GET', 'POST'])
def support_tickets(request):
    if request.method == 'POST':
        # Multipart uses a JSON string for the same bounded technical object.
        data = {key: request.data[key] for key in ('message', 'technical', 'image') if key in request.data}
        if isinstance(data.get('technical'), str):
            try:
                data['technical'] = json.loads(data['technical'])
            except ValueError:
                raise ValidationError('Thông tin kỹ thuật không hợp lệ.')
        form = TicketInput(data=data)
        form.is_valid(raise_exception=True)
        return Response(ticket_json(form.save(owner=request.user)), status=201)
    return Response({'items': [ticket_json(t) for t in SupportTicket.objects.filter(owner=request.user).select_related('owner')[:100]]})


@api_view(['GET'])
def ticket_image(request, ticket_id):
    qs = SupportTicket.objects.all() if request.user.is_superuser else SupportTicket.objects.filter(owner=request.user)
    ticket = get_object_or_404(qs, pk=ticket_id)
    if not ticket.image:
        return Response({'message': 'Không có ảnh đính kèm.'}, status=404)
    response = FileResponse(ticket.image.open('rb'), content_type='image/jpeg' if ticket.image.name.lower().endswith(('.jpg', '.jpeg')) else 'image/png')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@api_view(['GET'])
@permission_classes([NotificationAdmin])
def admin_tickets(request):
    return Response({'items': [ticket_json(t) for t in SupportTicket.objects.select_related('owner')[:200]]})


@api_view(['PATCH'])
@permission_classes([NotificationAdmin])
def admin_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    status_field = serializers.ChoiceField(choices=SupportTicket.STATUS_CHOICES)
    if 'status' in request.data:
        ticket.status = status_field.run_validation(request.data['status'])
    if 'admin_note' in request.data:
        ticket.admin_note = serializers.CharField(max_length=4000, allow_blank=True).run_validation(request.data['admin_note'])
    ticket.save(update_fields=['status', 'admin_note', 'updated_at'])
    return Response(ticket_json(ticket))
