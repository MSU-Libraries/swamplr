from django.conf.urls import include, url
from swamplr_namespaces import views

urlpatterns = [
    url(r'^$', views.load_namespaces, name="namespaces"),
    url(r'^$', views.load_namespaces, name="manage-namespaces"),
]



