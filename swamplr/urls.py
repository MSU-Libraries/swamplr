"""swamplr URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from swamplr_jobs import views
from django.conf import settings

urlpatterns = [
    url(r'^jobs/$', views.job_status, name='jobs'),
    url(r'^$', views.main, name='main'),
    url(r'^admin/', admin.site.urls),
    url(r'^remove/(?P<job_id>[0-9]+)/$', views.remove_job, name='remove_job'),
    url(r'^stop/(?P<job_id>[0-9]+)/$', views.stop_job, name='stop_job'),
    url(r'^job/(?P<job_id>[0-9]+)/$', views.view_job, name='view_job'),
]

if 'swamplr_services' in settings.INSTALLED_APPS:
    urlpatterns += [url(r'^services/', include('swamplr_services.urls'))]
if 'swamplr_ingest' in settings.INSTALLED_APPS:
    urlpatterns += [url(r'^ingest/', include('swamplr_ingest.urls'))]

