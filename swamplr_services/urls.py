from django.conf.urls import include, url
from swamplr_services import views

urlpatterns = [
    url(r'^add', views.add_service, name="add-service"),
    url(r'^manage', views.manage, name="manage-services"),
    url(r'^$', views.manage, name="services"), 
    url(r'^run/([0-9]{1,3})', views.run_service, name="run-services"),
    url(r'^delete/([0-9]{1,3})', views.delete_service, name="delete-services"),

]

