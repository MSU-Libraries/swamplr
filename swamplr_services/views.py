from django.shortcuts import render
from django.shortcuts import redirect
from apps import ServicesConfig
from models import services, service_jobs, service_status
from forms import ServicesForm
from swamplr_jobs.views import job_status, add_job
from swamplr_jobs.models import jobs
from datetime import datetime
import logging
import os
import shlex
import subprocess
from pwd import getpwnam

# Create your views here.

def manage(request, response={}):
    """Manage existing services and add new ones."""
    response.update(load_manage_data())
    return render(request, 'swamplr_services/manage.html', response)

def run_process(current_job):
    """Run process from swamplr_jobs.views."""

    service_job = service_jobs.objects.get(job_id=current_job)
    service = services.objects.get(service_id=service_job.service_id_id)
    service.last_started = current_job.started
    service.save()

    command = service.command
    user = service.run_as_user

    if not user:
        user = ServicesConfig.run_as_user

    user_id = getpwnam(user).pw_uid
    os.setuid(user_id)

    args = shlex.split(command)

    try:
        output = subprocess.check_output(args)
        status_id = service_status.objects.get(status="Success").service_status_id_id

    except Exception as e:
        output = e
        status_id = service_status.objects.get(status="Script error").service_status_id_id

    return (status_id, [output])

def pre_process():
    """Determine if there are any services that are scheduled to be run now.
        Also, check if there are any jobs to archive based on the auto_archive time field.
    """
    # Get the Jobs that are scheduled to be run
    # Based both on frequency/last_started as well as if they have 
    # active jobs running for that service
    pending_jobs = services.objects.raw("""
        SELECT DISTINCT s.* FROM swamplr_services_services s
        LEFT JOIN swamplr_services_service_jobs sj ON (s.service_id = sj.service_id_id)
        LEFT JOIN swamplr_jobs_jobs j ON (sj.job_id_id = j.job_id)
        LEFT JOIN swamplr_jobs_status t ON (t.status_id = j.status_id_id AND t.running='y')
        WHERE s.frequency IS NOT NULL
        AND ((NOW() >= DATE_ADD(s.last_started, INTERVAL s.frequency MINUTE) 
              AND t.status_id IS NULL)|| s.last_started IS NULL)
        AND s.archived != 'y'
    """);

    # Add new jobs for all services found
    logging.info("swamplr_services: Found {0} services that are scheduled to run.".format(len(list(pending_jobs))))
    for job in pending_jobs:
        logging.info("swamplr_service: Creating new job for service_id {0}".format(job.service_id))
        # Get service information from service id.
        service = services.objects.get(service_id=job.service_id)

        # Pass in app name from apps.py.
        new_job = add_job(ServicesConfig.name)

        new_service_job = service_jobs.objects.create(job_id=new_job, service_id=job)
        new_service_job.save()
	
    pending_archive = service_jobs.objects.raw("""
        SELECT DISTINCT sj.* FROM swamplr_services_services s
        LEFT JOIN swamplr_services_service_jobs sj ON (s.service_id = sj.service_id_id)
        LEFT JOIN swamplr_jobs_jobs j ON (j.job_id = sj.job_id_id)
        LEFT JOIN swamplr_jobs_status t ON (t.status_id = j.status_id_id AND t.success='y')
        WHERE s.auto_archive IS NOT NULL AND s.auto_archive > 0
        AND j.archived != 'y'
        AND DATE_ADD(j.completed, INTERVAL s.auto_archive MINUTE) <= NOW()
        AND t.success='y'
    """);

    # Archive each job
    logging.info("swamplr_services: Found {0} service jobs that can be archived.".format(len(list(pending_archive))))
    for job in pending_archive:
        logging.info("swamplr_service: Archiving {0}".format(job.job_id_id))
        jobs.objects.filter(job_id=job.job_id_id).update(archived='y')

def load_manage_data():
    """Load data for manage page."""
    service_objects = services.objects.exclude(archived='y')
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
             "auto_archive": s.auto_archive,
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
    if request.method != "POST":
        return redirect(manage)

    results_messages = ""
    error_messages = ""

    # Get service information from service id.
    service = services.objects.get(service_id=service_id)

    # Pass in app name from apps.py.
    new_job = add_job(ServicesConfig.name)

    new_service_job = service_jobs.objects.create(job_id=new_job, service_id=service)
    new_service_job.save()

    results_messages = ["Added job successfully."]

    return redirect(job_status) 

def add_service(request):
    """Add new service based on form input."""

    if request.method != "POST":
        return redirect(manage)
    response = {}

    # Check if form data is valid.
    form_data = ServicesForm(request.POST)
    if form_data.is_valid():

        new_service = services()
        new_service.archived = 'n'
        new_service.label = form_data.cleaned_data['label']
        new_service.description = form_data.cleaned_data['description'] 
        new_service.command = form_data.cleaned_data['command']
        
        if form_data.cleaned_data['frequency']:
            frequency = int(form_data.cleaned_data['frequency'])
            frequency_time  = form_data.cleaned_data['frequency_time']
            frequency = (frequency if frequency_time =='MIN' else frequency*60 if frequency_time =='HOUR' else  frequency*60*24 if frequency_time =='DAY' else  frequency*60*24*7 if frequency_time =='WEEK'  else 0)
            new_service.frequency = frequency
        
        if form_data.cleaned_data['auto_archive']:
            auto_archive = int(form_data.cleaned_data['auto_archive'])
            auto_archive_time  = form_data.cleaned_data['auto_archive_time']
            auto_archive = (auto_archive if auto_archive_time =='MIN' else auto_archive*60 if auto_archive_time =='HOUR' else  auto_archive*60*24 if auto_archive_time =='DAY' else  auto_archive*60*24*7 if auto_archive_time =='WEEK'  else 0)
            new_service.auto_archive = auto_archive

        new_service.run_as_user = form_data.cleaned_data['run_as_user']
        new_service.save()
        
        response["result_messages"] = ["New service successfully added."]

    else:

        response["error_messages"] = ["Failed to add service."]

    return redirect(manage)

def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id

    try:
        service = service_jobs.objects.get(job_id=job_id)
        service_info = services.objects.get(service_id=service.service_id_id)
        label = service_info.label

    # Cause of this exception would be the service being deleted from the table.
    except:
        label = "Not Found"

    info = ["Service name: {0}".format(label)]

    return info, []

def get_job_details(job):

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
        ("Auto Archive", service_info.auto_archive),
        ("Last Started", service_info.last_started),
    ]
    return details

def get_actions(job):
    """Required function: return actions to populate in job table."""
    actions = []

    stop_job = {
         "method": "POST",
         "label": "Stop Job",
         "action": "stop_job",
         "class": "btn-warning",
         "args": str(job.job_id)
    }

    archive_job = {
        "method": "POST",
        "label": "Remove Job",
        "action": "remove_job",
        "class": "btn-primary",
        "args": str(job.job_id)
    }

    if job.status.default == "y":
        actions.append(stop_job)

    elif not job.archived and job.status.default != 'y' and job.status.running != 'y':
        actions.append(archive_job)

    return actions

def delete_service(request, s_id):
    """Delete service based on id."""
    if request.method != "POST":
        return redirect(manage)

    services.objects.filter(service_id=s_id).update(archived='y')

    result_message = ["Successfully deleted service."]
    return redirect(manage)

def get_nav_bar():
    """Set contents of navigation bar for current app."""

    all_services = services.objects.all()
    nav = {"label": "Services",
           "name": "services"}
    
    return nav
