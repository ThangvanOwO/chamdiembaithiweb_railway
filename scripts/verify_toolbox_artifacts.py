"""Create clearly labeled QA examples, then verify A4 rendering preserves marker positions."""
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory, force_authenticate
from toolbox.reports import csv_report, xlsx_report, pdf_report
from toolbox.views import template_pdf


def main():
    output = ROOT / 'artifacts/toolbox_20261006'
    output.mkdir(parents=True, exist_ok=True)
    rows = [{'student_id': f'{index:06}', 'name': f'Nguyễn An {index}', 'class_name': '10A', 'classroom_id': 1,
             'variant_code': '101', 'score': round(5 + index / 20, 2) if index != 24 else None,
             'status': 'Đã có bài' if index != 24 else 'Chưa có bài', 'issues': [], 'reviewed': False}
            for index in range(1, 25)]
    data = {'exam_id': 1, 'exam_title': 'DỮ LIỆU MINH HỌA - Kiểm tra Toán 10', 'rows': rows,
            'summary': {'scored': 23, 'missing': 1, 'needs_review': 0, 'mean': 5.6, 'median': 5.6,
                        'min': 5.05, 'max': 6.15, 'missing_detail': 0}, 'questions': [
                {'variant_code': '101', 'part': 1, 'question': '1', 'subquestion': '', 'correct': 20,
                 'wrong': 2, 'unclear': 1, 'correct_rate': 90.91}]}
    (output / 'bang_diem_minh_hoa.pdf').write_bytes(pdf_report(data))
    (output / 'bang_diem_minh_hoa.xlsx').write_bytes(xlsx_report(data))
    (output / 'bang_diem_minh_hoa.csv').write_bytes(csv_report(data))
    # Authenticated read only, no test account or grades are inserted into the real DB.
    class QATeacher:
        is_authenticated = True
        is_active = True
    request = APIRequestFactory().get('/api/v1/templates/40-08-06/pdf/')
    force_authenticate(request, user=QATeacher())
    response = template_pdf(request, code='40-08-06')
    if response.status_code != 200:
        raise RuntimeError(f'Template PDF failed: {response.status_code}')
    (output / 'mau_40_08_06.pdf').write_bytes(response.content)
    print(f'Created QA examples in {output}')


if __name__ == '__main__':
    main()
