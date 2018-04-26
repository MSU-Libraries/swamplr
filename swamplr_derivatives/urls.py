from django.conf.urls import url
from swamplr_derivatives import views

urlpatterns = [
    url(r'^([a-zA-Z]{1,20})/submit', views.add_derivatives_job, name="add-derivatives-job"),
    url(r'^([a-zA-Z]{1,20})$', views.run_derivatives, name="run-derivatives"),
    url(r'^ajax/browse/$', views.browse, name='browse'),
]
