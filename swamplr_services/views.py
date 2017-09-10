from django.shortcuts import render
from models import services, service_jobs
from forms import ServicesForm
import logging

# Create your views here.

def reload_solr():
    pass

def reset_djatoka():
    pass


def manage(request):
    """Manage existing services and add new ones."""
    form = ServicesForm()
    response = {"form": form}   

    return render(request, 'swamplr_services/manage.html', response)

def run_service(service):
    """Run service given by name.
    Use name of service to retrieve it from a database.

    args:
        service(str): name of service to run.
    """
    return HttpResponse("Hello")

def add_service(request):

    form = ServicesForm()
    response = {"form": form}
    form_data = ServicesForm(request.POST)
    if form_data.is_valid():

        new_service = services()
        new_service.label = form_data.cleaned_data['label']
        new_service.description = form_data.cleaned_data['description'] 
        new_service.command = form_data.cleaned_data['command']
        new_service.run_as_user = form_data.cleaned_data['run_as_user']
        new_service.save()
        response["result_messages"] = ["New service successfully added."]

    else:
        response["error_messages"] = ["Failed to add service."]

    return render(request, 'swamplr_services/manage.html', response)


def get_nav_bar():
    """Set contents of navigation bar for current app."""

    all_services = services.objects.all()
    nav = {"label": "Services",
           "name": "services"}
    children = []
    for s in all_services:
        s_define = {"label": s.label,
                    "id": s.service_id}
        children.append(s_define)

    nav["children"] = children
    
    return nav
