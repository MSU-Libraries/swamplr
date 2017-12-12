from django.conf.urls import include, url
from swamplr_namespaces import views

urlpatterns = [
    url(r'^$', views.load_namespaces, name="namespaces"),
    url(r'^$', views.load_namespaces, name="manage-namespaces"),
    url(r'^list/([A-Za-z0-9\-\.\~\_\%]{1,64})$', views.list_items, name="list-items"),
    url(r'^reindex/([A-Za-z0-9\-\.\~\_\%]{1,64})$', views.reindex, name="reindex"),
    url(r'^delete/([A-Za-z0-9\-\.\~\_\%]{1,64})$', views.delete, name="delete"),
    url(r'^doi/([A-Za-z0-9\-\.\~\_\%]{1,64})$', views.mint_doi, name="mint_doi"),
    url(r'^ark/([A-Za-z0-9\-\.\~\_\%]{1,64})$', views.mint_ark, name="mint_ark"),
]



