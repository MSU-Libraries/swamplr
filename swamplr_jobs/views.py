from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from models import job_types, jobs, job_messages, status
import logging
import os
import importlib


APPS = [app for app in settings.INSTALLED_APPS if app.startswith("swamplr_")]

import_apps = {}

def main(request):
    """Landing page."""
    main = {}
    return render(request, 'swamplr_jobs/main.html', main)

def job_status(request, count=2):
    """Load job status page."""
    all_jobs = jobs.objects.all()
    paginator = Paginator(all_jobs, count)
    
    page = request.GET.get('page')
    
    try:
        job_list = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        job_list = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        job_list = paginator.page(paginator.num_pages) 

    for j in job_list.object_list:
        j.info = "test"
        j.status = status.objects.get(status_id=j.status_id_id)
        j.job_type = job_types.objects.get(type_id=j.type_id_id)
        
        app = import_apps[j.job_type.app_name]
        status_info = "No further info available."
        if hasattr(app.views, "get_status_info") and callable(getattr(app.views, "get_status_info")):
            status_info = app.views.get_status_info(j)
        j.status_info = status_info
        #TODO add actions: j.actions from app.views.get_actions 

    return render(request, 'swamplr_jobs/job_status.html', {"jobs": job_list})


def build_nav_bar():
    """Check installed apps for nav bar items."""
    nav_bar_items = []
    for app, data in import_apps.items():
        print hasattr(data, "get_nav_bar")
        if hasattr(data.views, "get_nav_bar") and callable(getattr(data.views, "get_nav_bar")):
            nav_bar_items.append(data.views.get_nav_bar())
    return nav_bar_items

def load_installed_apps():
    """Load contents of each installed app."""
    for app in APPS:
        import_apps[app] = importlib.import_module(app)

def add_job(app_name):
    """Use app_name to create new job."""
    # Get job type id for job type 'service'.
    job_type = job_types.objects.get(app_name=app_name)

    # Query for id of job status.
    job_status = status.objects.get(default="y")

    new_job = jobs.objects.create(type_id=job_type, created=timezone.now(), status_id=job_status)    
    new_job.save()

    return new_job

def process_job(current_job):
    """Initiate job and check for type.

    args:
        current_job(django query object): job data for the "next" job in the queue; that is,
            the job added first that is still in queued status.
    """
    result = (0, [])

    job_id = current_job.job_id

    # Get 'type' of current job to route it appropriately.
    type_obj = job_types.objects.get(type_id=current_job.type_id_id)

    status_obj = status.objects.get(running='y')

    load_installed_apps()

    current_job.status = status_obj
    current_job.started = timezone.now()
    current_job.process_id = os.getpid()
    current_job.save()
 
    logging.info("Starting Job ID: {0} for: {1}".format(job_id, type_obj.label))
    
    type_name = type_obj.app_name    

    if type_name in import_apps:
       
       app = import_apps[type_name]
       if hasattr(app.views, "run_process") and callable(getattr(app.views, "run_process")):
       
           result = app.views.run_process(current_job)
   
       else:
           message = ["Unable to process job: {0} app missing run_process function".format(type_name)]
           status_obj = status.objects.get(failure="error")
           result = (status_obj.status_id, message)
           
    else:
        message = ["Unable to process job: App doesn't exist: {0}".format(type_name)]
        status_obj = status.objects.get(failure="error")
        result = (status_obj.status_id, message)

    if result[1]:
        for message in result[1]:
            logging.info(message) 
            job_messages.objects.create(message=message, job_id=current_job, created=timezone.now()).save()

    status_obj = status.objects.get(status_id=result[0])
    current_job.status_id = status_obj 
    current_job.completed = timezone.now()
    current_job.save()


    
    
    
