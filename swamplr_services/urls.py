from django.conf.urls import include, url
from swamplr_services import views

urlpatterns = [
    url(r'^solr/reload/', views.reload_solr, name="reload_solr"),
    url(r'^djatoka/reset', views.reset_djatoka, name="reset_djatoka"),
]
