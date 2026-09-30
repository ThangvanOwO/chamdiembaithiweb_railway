"""Render UI-only fixtures with unsaved data; never reads or writes the database."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chamdiemtudong.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.urls import resolve

out = ROOT / "scratch" / "web_academic_qa"
out.mkdir(parents=True, exist_ok=True)
user = get_user_model()(username="ui-review", first_name="Thầy cô", last_name="GradeFlow", email="ui@example.test")
context = {
    "stats": {"total_exams": 0, "total_graded": 0, "today_graded": 0, "avg_score": None, "pass_rate": None},
    "recent_exams": [], "recent_submissions": [], "submissions": [], "exams": [],
    "templates": [], "templates_json": "[]", "distribution_json": json.dumps({"Giỏi": 0, "Khá": 0, "Trung bình": 0, "Yếu": 0}),
    "selected_template": "QM2025", "selected_exam": None, "template_info": None,
}
fixtures = {
    "dashboard": ("/dashboard/", "dashboard/index.html"),
    "upload": ("/grading/upload/", "grading/upload.html"),
    "import": ("/grading/exams/import/", "grading/exam_import.html"),
    "exams": ("/grading/exams/", "grading/exams.html"),
}
with override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
    for name, (url, template) in fixtures.items():
        request = RequestFactory().get(url)
        request.user = user
        request.resolver_match = resolve(url)
        (out / f"{name}.html").write_text(render_to_string(template, context, request=request), encoding="utf-8")
print(f"Rendered {len(fixtures)} database-free UI fixtures to {out}")
