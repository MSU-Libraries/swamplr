from django.conf.urls import include, url
from swamplr_ingest import views

urlpatterns = [
    url(r'^run/([a-z]{1,20})', views.run_ingest, name="run-ingest"),
    url(r'^manage', views.manage, name="manage-ingest"),
]

