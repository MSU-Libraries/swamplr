from django.shortcuts import render
from apps import ServicesConfig
from models import services, service_jobs, service_status
from forms import ServicesForm
from swamplr_jobs.views import add_job
from datetime import datetime
import logging

# Create your views here.

def manage(request, response={}):
    """Manage existing services and add new ones."""
    response.update(load_manage_data())
    return render(request, 'swamplr_services/manage.html', response)

def run_process(current_job):
    """Run process from swamplr_jobs.views."""
    
    status_id = service_status.objects.get(status="Success").service_status_id_id
    messages = ["SUCCESS - SOmETHING HAS WORKED"]

    return (status_id, messages)

def load_manage_data():
    """Load data for manage page."""
    service_objects = services.objects.all()
    all_services = []

    for s in service_objects:

        all_services.append(
            {
             "id": s.service_id,
             "label": s.label,
             "description": s.description,
             "command": s.command,
             "run_as_user": s.run_as_user,
            }
        )    

    form = ServicesForm()
    response = {
        "form": form,
        "services": all_services,
    }   
    return response

def run_service(request, service_id):
    """Run service given by name.
    Use id of service to retrieve it from a database.

    args:
        service_id(str): id of service to run.
    """
    
    results_messages = ""
    error_messages = ""

    # Get service information from service id.
    service = services.objects.get(service_id=service_id)

    # Pass in app name from apps.py.
    new_job = add_job(ServicesConfig.name)

    new_service_job = service_jobs.objects.create(job_id=new_job, service_id=service)
    new_service_job.save()

    results_messages = ["Added job successfully."]

    return manage(request, response={"results_messages": results_messages, "error_messages": error_messages})

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

    return manage(request, response=response)

def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id
    service = service_jobs.objects.get(job_id=job.job_id)
    service_info = services.objects.get(service_id=service.service_id_id)
    
    info = ["Service name: {0}".format(service_info.label)]

    return info

def get_actions(job):
    """Required function: return actions to populate in job table."""
    actions = []
    return actions

def delete_service(request, s_id):
    """Delete service based on id."""
    services.objects.filter(service_id=s_id).delete()
    result_message = ["Successfully deleted service."]
    return manage(request, response={"result_messages": result_message})    

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
