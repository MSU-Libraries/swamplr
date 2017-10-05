from django.shortcuts import render
from django.http import HttpResponse
from apps import SwamplrIngestConfig
from models import ingest_jobs
from forms import IngestForm
from swamplr_jobs.views import add_job
from datetime import datetime
import logging
import os
import json

def manage(request, response={}):
    """Manage existing services and add new ones."""
    response.update(load_manage_data())
    return render(request, 'swamplr_services/manage.html', response)

#def run_process(current_job):
#    """Run process from swamplr_jobs.views."""
#
#    service_job = service_jobs.objects.get(job_id=current_job)
#    service = services.objects.get(service_id=service_job.service_id_id)
#    service.last_started = current_job.started
#    service.save()
#
#    command = service.command
#    user = service.run_as_user
#
#    if not user:
#        user = ServicesConfig.run_as_user
#
#    user_id = getpwnam(user).pw_uid
#    os.setuid(user_id)
#
#    args = shlex.split(command)
#
#    try:
#        output = subprocess.check_output(args)
#        status_id = service_status.objects.get(status="Success").service_status_id_id
#
#    except Exception as e:
#        output = e
#        status_id = service_status.objects.get(status="Script error").service_status_id_id
#
#    return (status_id, [output])
#
def add_ingest_job(request):
    
    form = IngestForm(request.POST)
    if form.is_valid():
        clean = form.cleaned_data
        
        new_job = add_job(SwamplrIngestConfig.name)
        ingest_job = ingest_jobs.objects.create(
            job_id=new_job,
            source_dir=clean["source_dir"]            


def run_ingest(request, collection_name):
   
    form = IngestForm()
    form.set_fields(collection_name)
    form.set_form_action(collection_name)
    return render(request, "swamplr_ingest/ingest.html", {"form": form})


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
             "frequency": s.frequency,
             "last_started": s.last_started,
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

    return manage(request, response={"result_messages": results_messages, "error_messages": error_messages})

def add_service(request):

    form = ServicesForm()
    response = {"form": form}
    form_data = ServicesForm(request.POST)
    if form_data.is_valid():

        new_service = services()
        new_service.label = form_data.cleaned_data['label']
        new_service.description = form_data.cleaned_data['description'] 
        new_service.command = form_data.cleaned_data['command']
        if form_data.cleaned_data['frequency']:
            frequency = int(form_data.cleaned_data['frequency'])
            frequency_time  = form_data.cleaned_data['frequency_time']
            frequency = (frequency if frequency_time =='MIN' else frequency*60 if frequency_time =='HOUR' else  frequency*60*24 if frequency_time =='DAY' else  frequency*60*24*7 if frequency_time =='WEEK'  else 0)
            new_service.frequency = frequency
        new_service.run_as_user = form_data.cleaned_data['run_as_user']
        new_service.save()
        response["result_messages"] = ["New service successfully added."]

    else:
        response["error_messages"] = ["Failed to add service."]

    return manage(request, response=response)

def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id

    try:
        service = service_jobs.objects.get(job_id=job.job_id)
        service_info = services.objects.get(service_id=service.service_id_id)
        label = service_info.label
        details = [
            ("Service ID", service_info.service_id),
            ("Label", label),
            ("Description", service_info.description),
            ("Command", service_info.command),
            ("User", service_info.run_as_user),
            ("Frequency", service_info.frequency),
            ("Last Started", service_info.last_started),
        ]

    # Cause of this exception would be the service being deleted from the table.
    except:
        label = "Not Found"
        details = [("None", "No Info Found")]

    info = ["Service name: {0}".format(label)]

    return info, details


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
    nav = {"label": "Ingest",
           "name": "ingest"}
    nav["children"] = get_ingest_options()
    return nav

def get_ingest_options(status=["active"]):
    """Use configs to get options to use in ingest."""

    ingest_options = []

    data = load_ingest_data()

    for ingest_type, values in data.items():
        if values["status"] in status:
            d_settings = {
                "label": values["label"],
                "id": values["name"],
            }
            ingest_options.append(d_settings)

    return ingest_options


def get_ingest_data(ingest_type):
    """Load ingest data and return values based on type.

    args:
        ingest_type(str): ingest type or collection name. Should match
            config key.
    """
    data = load_ingest_data()
    return data[ingest_type]


def load_ingest_data():
    """Load json file of collection data."""
    config_path = SwamplrIngestConfig.collection_configs
    with open(config_path) as configs:
        data = json.load(configs)
    return data

