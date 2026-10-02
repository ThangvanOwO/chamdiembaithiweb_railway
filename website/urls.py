from django.urls import path
from django.views.generic import TemplateView

from . import views


app_name = "website"

urlpatterns = [
    path("ads.txt", TemplateView.as_view(template_name="website/ads.txt", content_type="text/plain; charset=utf-8"), name="ads_txt"),
    path("app-ads.txt", TemplateView.as_view(template_name="website/ads.txt", content_type="text/plain; charset=utf-8"), name="app_ads_txt"),
    path("robots.txt", TemplateView.as_view(template_name="website/robots.txt", content_type="text/plain; charset=utf-8"), name="robots_txt"),
    path("sitemap.xml", TemplateView.as_view(template_name="website/sitemap.xml", content_type="application/xml; charset=utf-8"), name="sitemap"),
    path("", views.home, name="home"),
    path("huong-dan/", views.guide, name="guide"),
    path("chinh-sach-bao-mat/", views.privacy, name="privacy"),
    path("xoa-tai-khoan/", views.account_deletion, name="account_deletion"),
    path("tai-ung-dung/", views.download, name="download"),
    path("downloads/gradeflow.apk", views.apk_download, name="apk_download"),
]
