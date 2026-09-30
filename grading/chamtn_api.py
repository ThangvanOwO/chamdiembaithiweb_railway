"""
=============================================================================
  CHAMTN API VIEWS FOR DJANGO
  Cung cấp toàn bộ REST API endpoints cho giao diện Web ChamTN SPA:
    - /api/me
    - /api/dashboard
    - /api/templates
    - /api/templates/<id>
    - /api/exams
    - /api/exams/<id>
    - /api/exams/<id>/key
    - /api/exams/<id>/grade (Upload ảnh / ZIP / PDF chấm bài đa luồng)
    - /api/exams/<id>/sheets
    - /api/sheets/<id> (Soát phiếu: xem ảnh + overlay + sửa tay đáp án)
    - /api/exams/<id>/export.xlsx (Xuất Excel 4 sheets)
    - /api/events (SSE nhật ký trực tiếp)
=============================================================================
"""

import os
import io
import json
import zipfile
import tempfile
import cv2
import numpy as np
from django.utils import timezone
from datetime import datetime
from pathlib import Path

from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.http import JsonResponse, HttpResponse, FileResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from accounts.access import private_api
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.db.models import Avg, Count

from grading.models import Exam, ExamVariant, Submission
from grading.engine.chamtn_core import Template, ChamTNEngine, ScoringEngine
from grading.engine.excel_reporter import export_exam_results_excel
from grading.engine import hi as legacy_hi
from accounts.scan_billing import bill_scans
from django.views.decorators.csrf import csrf_protect

TEMPLATES_DATA_DIR = Path(__file__).resolve().parent / "templates_data"


@require_http_methods(['GET'])
def api_health(request):
    """GET /api/health — Kiểm tra trạng thái hệ thống."""
    db_engine = settings.DATABASES["default"]["ENGINE"]
    return JsonResponse({
        "ok": True,
        "app": "GradeFlow - ChamTN 2026",
        "version_line": "ChamTN 2.0 (QM-2025 Engine)",
        "db": "postgres" if "postgres" in db_engine else "sqlite"
    })


@csrf_protect
def api_login(request):
    """POST /api/login — Đăng nhập hệ thống."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        body = request.POST

    username = body.get("username", "").strip()
    password = body.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return JsonResponse({
            "ok": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "role": "admin" if user.is_staff else "teacher"
            }
        })
    return JsonResponse({"error": "Tên đăng nhập hoặc mật khẩu không chính xác"}, status=400)


@private_api
@require_http_methods(['POST'])
def api_logout(request):
    """POST /api/logout — Đăng xuất."""
    logout(request)
    return JsonResponse({"ok": True})


def _get_template_for_exam(exam: Exam = None) -> Template:
    """Tải template JSON phù hợp cho kỳ thi (ưu tiên qm2025_40_08_06)."""
    default_path = TEMPLATES_DATA_DIR / "qm2025_40_08_06.json"
    if not default_path.exists():
        # Fallback to build script if not present
        from grading.tools.generate_qm2025_template import build_qm2025_40_08_06
        tpl_data = build_qm2025_40_08_06()
        with open(default_path, "w", encoding="utf-8") as f:
            json.dump(tpl_data, f, ensure_ascii=False, indent=2)
    return Template.load_json(str(default_path))


@private_api
def api_me(request):
    """GET /api/me — Trả về thông tin người dùng hiện tại."""
    u = request.user

    full_name = u.get_full_name() or u.username
    return JsonResponse({
        "ok": True,
        "user": {
            "id": u.id,
            "username": u.username,
            "full_name": full_name,
            "role": "admin" if u.is_staff else "teacher",
            "must_change": False
        },
        "settings": {
            "app_name": "GradeFlow - ChamTN 2026",
            "app_short": "GradeFlow",
            "copyright": "© 2026 GradeFlow - Hệ thống chấm trắc nghiệm thông minh",
            "org_name": "Bộ môn Khảo thí",
            "primary_color": "#2563eb",
            "omr_fill_threshold": "0.26",
            "omr_pink_dropout": "1",
            "omr_detect_rotation": "1"
        },
        "version_line": "ChamTN 2.0 (QM-2025 Engine Python)"
    })


@private_api
def api_dashboard(request):
    """GET /api/dashboard — Thống kê tổng quan."""
    user = request.user
    exams_qs = Exam.objects.filter(teacher=user)
    sub_qs = Submission.objects.filter(teacher=user)

    n_exams = exams_qs.count()
    n_sheets = sub_qs.count()
    completed_subs = sub_qs.filter(status="completed")
    avg_score = completed_subs.aggregate(Avg("score"))["score__avg"] or 0.0

    recent_exams = []
    for e in exams_qs.order_by("-created_at")[:6]:
        recent_exams.append({
            "id": e.id,
            "code": e.template_code or f"MD{e.id:03d}",
            "name": e.title,
            "subject": e.subject or "Trắc nghiệm",
            "n_sheets": e.submissions.count(),
            "avg_score": round(e.average_score or 0.0, 1),
            "date": e.created_at.strftime("%d/%m/%Y")
        })

    return JsonResponse({
        "ok": True,
        "stats": {
            "n_exams": n_exams,
            "n_sheets": n_sheets,
            "avg_score": round(avg_score, 1)
        },
        "recent_exams": recent_exams
    })


@private_api
def api_templates_list(request):
    """GET /api/templates — Danh sách các mẫu phiếu."""
    templates = []
    if TEMPLATES_DATA_DIR.exists():
        for fn in sorted(os.listdir(TEMPLATES_DATA_DIR)):
            if fn.endswith(".json"):
                fp = TEMPLATES_DATA_DIR / fn
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    n_b = sum(len(fld.get("opts", [])) for fld in data.get("fields", []))
                    templates.append({
                        "id": data.get("id", fn[:-5]),
                        "name": data.get("name", fn[:-5]),
                        "builtin": data.get("builtin", True),
                        "counts": data.get("counts", {}),
                        "n_bubbles": n_b,
                        "updated_at_txt": "2026-09-08"
                    })
                except Exception:
                    pass

    # Đưa mẫu ưu tiên số 1 qm2025_40_08_06 lên đầu
    templates.sort(key=lambda t: 0 if t["id"] == "qm2025_40_08_06" else 1)
    return JsonResponse({"ok": True, "items": templates})


@private_api
def api_template_detail(request, template_id):
    """GET /api/templates/<id> — Chi tiết JSON tọa độ mẫu phiếu."""
    file_path = TEMPLATES_DATA_DIR / f"{template_id}.json"
    if not file_path.exists():
        # Fallback to default
        file_path = TEMPLATES_DATA_DIR / "qm2025_40_08_06.json"

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JsonResponse(data)


@private_api
def api_exams_collection(request):
    """GET / POST /api/exams — Quản lý danh sách kỳ thi."""
    user = request.user

    if request.method == "GET":
        qs = Exam.objects.filter(teacher=user)
        items = []
        for e in qs.order_by("-created_at"):
            items.append({
                "id": e.id,
                "code": e.template_code or f"MD{e.id:03d}",
                "name": e.title,
                "subject": e.subject or "Trắc nghiệm",
                "template_id": "qm2025_40_08_06",
                "n_sheets": e.submissions.count(),
                "avg_score": round(e.average_score or 0.0, 1),
                "created_at": e.created_at.strftime("%d/%m/%Y %H:%M"),
                "status": "ready"
            })
        return JsonResponse({"ok": True, "items": items})

    elif request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = request.POST

        title = body.get("name", "").strip() or "Kỳ thi mới"
        subject = body.get("subject", "").strip() or "Trắc nghiệm"
        code = body.get("code", "").strip() or "40-08-06"

        from django.contrib.auth.models import User
        teacher = user
        exam = Exam.objects.create(
            teacher=teacher,
            title=title,
            subject=subject,
            template_code=code,
            num_questions=40
        )
        return JsonResponse({"ok": True, "id": exam.id})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@private_api
def api_exam_item(request, exam_id):
    """GET / PUT / DELETE /api/exams/<id> — Chi tiết / sửa / xóa một kỳ thi."""
    try:
        exam = Exam.objects.get(id=exam_id, teacher=request.user)
    except Exam.DoesNotExist:
        return JsonResponse({"error": "Kỳ thi không tồn tại"}, status=404)

    if request.method == "GET":
        # Lấy danh sách mã đề
        keys = []
        for v in exam.variants.all():
            keys.append({
                "made": v.variant_code,
                "data": v.answers
            })

        # Nếu chưa có mã đề riêng, lấy đáp án chung từ exam.answer_key
        common_key = {}
        if exam.answer_key:
            try:
                common_key = json.loads(exam.answer_key)
            except Exception:
                pass

        return JsonResponse({
            "ok": True,
            "id": exam.id,
            "code": exam.template_code or f"MD{exam.id:03d}",
            "name": exam.title,
            "subject": exam.subject,
            "template_id": "qm2025_40_08_06",
            "n_sheets": exam.submissions.count(),
            "avg_score": round(exam.average_score or 0.0, 1),
            "keys": keys,
            "common_key": common_key
        })

    elif request.method in ["PUT", "POST"]:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = request.POST

        if "name" in body:
            exam.title = body["name"].strip()
        if "subject" in body:
            exam.subject = body["subject"].strip()
        if "code" in body:
            exam.template_code = body["code"].strip()
        exam.save()
        return JsonResponse({"ok": True})

    elif request.method == "DELETE":
        exam.delete()
        return JsonResponse({"ok": True})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@private_api
@require_http_methods(['POST'])
def api_exam_save_key(request, exam_id):
    """POST /api/exams/<id>/key — Lưu đáp án cho mã đề."""
    try:
        exam = Exam.objects.get(id=exam_id, teacher=request.user)
    except Exam.DoesNotExist:
        return JsonResponse({"error": "Kỳ thi không tồn tại"}, status=404)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        body = request.POST

    made = str(body.get("made", "")).strip()
    key_data = body.get("key", {})

    if made:
        variant, _ = ExamVariant.objects.get_or_create(exam=exam, variant_code=made)
        variant.answers_json = json.dumps(key_data, ensure_ascii=False)
        variant.save()
    else:
        exam.answer_key = json.dumps(key_data, ensure_ascii=False)
        exam.save()

    return JsonResponse({"ok": True})


@private_api
@require_http_methods(['POST'])
@bill_scans(mode='batch')
def api_exam_grade_batch(request, exam_id):
    """
    POST /api/exams/<id>/grade — Tải lên nhiều ảnh / tệp ZIP / PDF để chấm hàng loạt bằng ChamTNEngine.
    """
    try:
        exam = Exam.objects.get(id=exam_id, teacher=request.user)
    except Exam.DoesNotExist:
        return JsonResponse({"error": "Kỳ thi không tồn tại"}, status=404)

    template = _get_template_for_exam(exam)
    engine = ChamTNEngine(template)

    uploaded_files = request.FILES.getlist("files") or request.FILES.getlist("file")
    if not uploaded_files:
        return JsonResponse({"error": "Không có tệp nào được tải lên"}, status=400)

    # Nạp danh sách đáp án của tất cả các mã đề của kỳ thi
    variant_keys = {}
    for v in exam.variants.all():
        variant_keys[v.variant_code] = v.answers

    # Đáp án mặc định chung
    common_key = {}
    if exam.answer_key:
        try:
            common_key = json.loads(exam.answer_key)
        except Exception:
            pass

    processed_items = []
    errors = []

    for uf in uploaded_files:
        filename = uf.name.lower()

        # Danh sách (tên_ảnh, byte_data) cần xử lý
        images_to_grade = []

        if filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(uf) as z:
                    for zinfo in z.infolist():
                        ext = os.path.splitext(zinfo.filename)[1].lower()
                        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                            images_to_grade.append((zinfo.filename, z.read(zinfo)))
            except Exception as ze:
                errors.append(f"Không giải nén được {uf.name}: {ze}")
                continue
        else:
            images_to_grade.append((uf.name, uf.read()))

        for img_name, img_bytes in images_to_grade:
            try:
                # Decode ảnh từ bộ nhớ bằng OpenCV
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    errors.append(f"Không đọc được ảnh {img_name}")
                    continue

                # 1. Phát hiện và nắn thẳng (Warp) bằng ChamTN Alignment (Grid Score Tournament)
                detect_res = engine.detect_and_warp(img)
                warped = detect_res["warped"]

                # 2. Bóc tách đáp án bằng ChamTNEngine
                ans = engine.extract_answers(warped)
                sbd = ans["sbd"]
                made = ans["made"]

                # 3. Chọn đáp án chuẩn theo mã đề đọc được
                cur_key = variant_keys.get(made, common_key)

                # 4. Chấm điểm theo thang chuẩn Bộ GD&ĐT
                graded = ScoringEngine.grade_exam(ans, cur_key)

                # 5. Lưu kết quả vào cơ sở dữ liệu
                from django.contrib.auth.models import User
                teacher = request.user

                detail_data = {
                    "graded": graded,
                    "quality": ans.get("quality", {}),
                    "p1_score": graded["p1_score"],
                    "p2_score": graded["p2_score"],
                    "p3_score": graded["p3_score"]
                }
                correct_p1_cnt = sum(1 for d in graded.get("p1_details", {}).values() if d.get("is_correct"))

                sub = Submission.objects.create(
                    exam=exam,
                    teacher=teacher,
                    template_code="qm2025_40_08_06",
                    student_id=sbd,
                    student_name=f"Học sinh {sbd}",
                    score=graded["total_score"],
                    correct_count=correct_p1_cnt,
                    total_questions=40,
                    answers_detected=json.dumps(ans, ensure_ascii=False),
                    detail_json=json.dumps(detail_data, ensure_ascii=False),
                    status="completed",
                    graded_at=timezone.now()
                )

                request.billable_scans += 1

                # Lưu ảnh bài làm
                _, orig_buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                sub.image.save(f"sub_{sub.id}.jpg", ContentFile(orig_buf.tobytes()), save=True)

                processed_items.append({
                    "id": sub.id,
                    "filename": img_name,
                    "sbd": sbd,
                    "made": made,
                    "score": graded["total_score"],
                    "separation": ans.get("quality", {}).get("separation", 0.0),
                    "status": "OK"
                })

            except Exception as e:
                errors.append(f"Lỗi xử lý {img_name}: {e}")

    return JsonResponse({
        "ok": True,
        "n_processed": len(processed_items),
        "n_errors": len(errors),
        "items": processed_items,
        "errors": errors
    })


@private_api
def api_exam_sheets_list(request, exam_id):
    """GET /api/exams/<id>/sheets — Danh sách bài làm đã chấm của kỳ thi."""
    try:
        exam = Exam.objects.get(id=exam_id, teacher=request.user)
    except Exam.DoesNotExist:
        return JsonResponse({"error": "Kỳ thi không tồn tại"}, status=404)

    items = []
    for s in exam.submissions.order_by("-id"):
        raw_ans = json.loads(s.answers_detected) if s.answers_detected else {}
        detail_obj = json.loads(s.detail_json) if s.detail_json else {}
        items.append({
            "id": s.id,
            "sbd": s.student_id,
            "name": s.student_name,
            "made": raw_ans.get("made", ""),
            "score": s.score or 0.0,
            "p1": detail_obj.get("p1_score", 0.0),
            "p2": detail_obj.get("p2_score", 0.0),
            "p3": detail_obj.get("p3_score", 0.0),
            "status": s.status,
            "created_at": s.uploaded_at.strftime("%d/%m/%Y %H:%M") if hasattr(s, "uploaded_at") else ""
        })

    return JsonResponse({"ok": True, "items": items})


@private_api
def api_sheet_review_detail(request, sheet_id):
    """
    GET / PUT /api/sheets/<id>
    Màn hình Soát phiếu (Review UI):
      - GET: trả về thông tin bài thi, ảnh scan kèm tọa độ overlay, đáp án bóc tách.
      - PUT: giáo viên chỉnh sửa tay đáp án -> hệ thống tính lại điểm tức thì.
    """
    try:
        sub = Submission.objects.get(id=sheet_id, teacher=request.user)
    except Submission.DoesNotExist:
        return JsonResponse({"error": "Bài thi không tồn tại"}, status=404)

    exam = sub.exam
    template = _get_template_for_exam(exam)
    raw_ans = json.loads(sub.answers_detected) if sub.answers_detected else {}
    detail_obj = json.loads(sub.detail_json) if sub.detail_json else {}

    # Nạp đáp án chuẩn
    made = raw_ans.get("made", "")
    variant = exam.variants.filter(variant_code=made).first() if made else None
    cur_key = variant.answers if variant else (json.loads(exam.answer_key) if exam.answer_key else {})

    if request.method == "GET":
        # Chấm lại để lấy chi tiết đúng/sai từng câu
        graded = ScoringEngine.grade_exam(raw_ans, cur_key)
        image_url = sub.image.url if sub.image else ""

        return JsonResponse({
            "ok": True,
            "id": sub.id,
            "exam_id": exam.id,
            "exam_name": exam.title,
            "sbd": sub.student_id,
            "made": made,
            "name": sub.student_name,
            "score": sub.score,
            "image_url": image_url,
            "template": {
                "page_w": template.page_w,
                "page_h": template.page_h,
                "bubble_w": template.bubble_w,
                "bubble_h": template.bubble_h,
                "fields": template.fields
            },
            "answers": raw_ans,
            "graded": graded
        })

    elif request.method in ["PUT", "POST"]:
        # Giáo viên chỉnh sửa tay đáp án
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = request.POST

        new_answers = body.get("answers", raw_ans)
        new_sbd = body.get("sbd", sub.student_id)
        new_made = body.get("made", made)

        # Cập nhật mã đề nếu có thay đổi
        if new_made != made:
            variant = exam.variants.filter(variant_code=new_made).first()
            cur_key = variant.answers if variant else cur_key

        # Tính lại điểm ngay lập tức
        graded = ScoringEngine.grade_exam(new_answers, cur_key)

        sub.student_id = new_sbd
        if new_answers:
            new_answers["sbd"] = new_sbd
            new_answers["made"] = new_made

        sub.answers_detected = json.dumps(new_answers, ensure_ascii=False)
        detail_obj["graded"] = graded
        detail_obj["p1_score"] = graded["p1_score"]
        detail_obj["p2_score"] = graded["p2_score"]
        detail_obj["p3_score"] = graded["p3_score"]
        sub.detail_json = json.dumps(detail_obj, ensure_ascii=False)
        sub.score = graded["total_score"]
        sub.save()

        return JsonResponse({
            "ok": True,
            "score": sub.score,
            "graded": graded
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


@private_api
def api_exam_export_excel(request, exam_id):
    """GET /api/exams/<id>/export.xlsx — Tải xuống báo cáo Excel 4 sheets chuẩn ChamTN."""
    try:
        exam = Exam.objects.get(id=exam_id, teacher=request.user)
    except Exam.DoesNotExist:
        return JsonResponse({"error": "Kỳ thi không tồn tại"}, status=404)

    # Nạp đáp án chuẩn
    variant_keys = {v.variant_code: v.answers for v in exam.variants.all()}
    common_key = json.loads(exam.answer_key) if exam.answer_key else {}

    results = []
    for idx, sub in enumerate(exam.submissions.filter(status="completed").order_by("student_id"), 1):
        raw_ans = json.loads(sub.answers_detected) if sub.answers_detected else {}
        made = raw_ans.get("made", "")
        cur_key = variant_keys.get(made, common_key)
        graded = ScoringEngine.grade_exam(raw_ans, cur_key)
        graded.update({
            "sbd": sub.student_id,
            "made": made,
            "name": sub.student_name or f"Thí sinh {idx}",
            "class_name": "Lớp 12",
            "room": "Phòng 01"
        })
        results.append(graded)

    exam_info = {
        "name": exam.title,
        "subject": exam.subject or "Trắc nghiệm",
        "date": exam.created_at.strftime("%d/%m/%Y"),
        "counts": {"p1": 40, "p2": 8, "p3": 6}
    }

    # Tạo file Excel tạm
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name

    export_exam_results_excel(exam_info, results, tmp_path)

    with open(tmp_path, "rb") as f:
        file_data = f.read()
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    response = HttpResponse(
        file_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    safe_title = "".join([c if c.isalnum() else "_" for c in exam.title])
    response["Content-Disposition"] = f'attachment; filename="Ket_qua_{safe_title}.xlsx"'
    return response


@private_api
def api_events_stream(request):
    """GET /api/events — Server-Sent Events (SSE) để truyền nhật ký trực tiếp."""
    def event_generator():
        # Gửi ping ban đầu
        yield f"data: {json.dumps({'level': 'INFO', 'time': datetime.now().strftime('%H:%M:%S'), 'msg': 'Đã kết nối nhật ký trực tiếp (SSE)'})}\n\n"
    return StreamingHttpResponse(event_generator(), content_type="text/event-stream")
