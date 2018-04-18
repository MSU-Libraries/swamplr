from django.conf.urls import include, url
from swamplr_ingest import views

urlpatterns = [
    url(r'^([a-z]{1,20})/submit', views.add_ingest_job, name="add-ingest-job"),
    url(r'^manage', views.manage, name="manage-ingest"),
    url(r'^([a-z]{1,20})$', views.run_ingest, name="run-ingest"),
    url(r'^ajax/browse/$', views.browse, name='browse'),
    url(r'^delete/job/(?P<source_job_id>[0-9]+)/$', views.add_delete_job, name='delete-new'),
    url(r'^pathauto/job/(?P<source_job_id>[0-9]+)/$', views.add_pathauto_job, name='pathauto-job'),
]

