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

def job_status(request, count=25, response={}):
    """Load job status page."""
    load_installed_apps()

    response["headings"] = ["Job ID", "Job Type", "Details", "Created", "Completed", "Status", "Actions"]

    all_jobs = jobs.objects.all().exclude(archived="y").order_by('-created')
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

    job_data = []
    for j in job_list.object_list:
        
        j = set_job_info(j)
        #job_data.append(j_updated)

    response["jobs"] = job_list

    return render(request, 'swamplr_jobs/job_status.html', response)

def view_job(request, job_id):
    """View full details for job."""
    load_installed_apps()
    
    job = jobs.objects.get(job_id=job_id)
    job_type_object = job_types.objects.get(type_id=job.type_id_id)
    
    job = set_job_info(job)
    if job.completed:
        elapsed = job.completed - job.created
    else:
        elapsed = timezone.now() - job.created
    job.card = [
        ("Job ID", job_id),
        ("Job Type", job_type_object.label),
        ("App", job_type_object.app_name),
        ("Status", job.status.status),
        ("Created", job.created),
        ("Started", job.started),
        ("Completed", job.completed),
        ("Elapsed", elapsed),
        ("Status Info", job.status_info),
    ]
 
    job.messages = []
    message_object = job_messages.objects.filter(job_id=job)
    for m in message_object:
        mcontent = m.message
        mtime = m.created
        job.messages.append((mtime, mcontent))

    job.objects = []
    #TODO - get objects.

    return render(request, 'swamplr_jobs/job.html', {"job": job})

def set_job_info(j):
    """Get job data for display."""

    j.status = status.objects.get(status_id=j.status_id_id)
    job_type_object = job_types.objects.get(type_id=j.type_id_id)

    job_type = job_type_object.label
    app_name = job_type_object.app_name

    j.job_type = job_type
    d = import_apps
    app = import_apps[app_name]
    
    status_info = "No further info available."
    if hasattr(app.views, "get_status_info") and callable(getattr(app.views, "get_status_info")):
        status_info, details = app.views.get_status_info(j)
        j.status_info = "<br/>".join(status_info)
        j.details = details 

    actions = set_default_actions(j)
    if hasattr(app.views, "get_actions") and callable(getattr(app.views, "get_actions")):
        app_actions = app.views.get_actions(j)

    actions += app_actions
    j.actions = actions
    
    return j

def set_default_actions(job):
    """Set default actions for jobs."""
    actions = []
    stop_job = {
         "label": "Stop Job",
         "action": "stop_job",
         "class": "btn-danger",
         "args": str(job.job_id)
        }
    rerun_job = {
        "label": "Run same job",
        "action": "add_job",
        "class": "btn-info",
        "args": str(job.job_id),
        }

    archive_job = {
        "label": "Remove Job",
        "action": "remove_job",
        "class": "btn-secondary",
        "args": str(job.job_id)
    }

    if job.status.default == "y" or job.status.running == "y":
        actions.append(stop_job)

    elif not job.archived:
        actions.append(archive_job)

    #TODO: Add default re-run job button.
 
    return actions

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

def pre_process():
    """ Check each installed app to see if they have any steps to run before processing
        to be run every time, even if there are no pending jobs for it.
    """
    load_installed_apps()
    for app_name in import_apps:
        if app_name == "swamplr_jobs":
            continue
        app = import_apps[app_name]
        logging.info("Checking {0} for pre_process function.".format(app_name))
        if hasattr(app.views, "pre_process") and callable(getattr(app.views, "pre_process")):
             app.views.pre_process()

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

    current_job.status_id = status_obj
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

def remove_job(request, job_id):
    """Remove aka "archive" job."""
    job_object = jobs.objects.get(job_id=job_id)
    job_object.archived = "y"
    job_object.save()
    return job_status(request, response={"result_messages": ["Job ID #{0} successfully removed.".format(job_id)]})
   
def stop_job(request, job_id):
    
    result_message = []
    error_message = []
    job_object = jobs.objects.get(job_id=job_id)
    status_obj = status.objects.get(failure="manual")
    job_object.status_id = status_obj 
    job_object.save()

    if job_object.process_id != 0:
        # Attempt to kill job 'nicely'.
        try:
            os.kill(job_object.process_id, 15)
            logging.info("Job ID #{0} successfully canceled.".format(job_id))
            result_message = ["Job ID #{0} successfully canceled.".format(job_id)]
        except:
            error_message = ["Unable to cancel job {0} at process ID: {1}".format(job_id, job_object.process_id)]
            logging.warning("Unable to cancel job {0} at process ID: {1}".format(job_id, job_object.process_id))

    else:

        logging.info("Job ID #{0} successfully canceled.".format(job_id))
        result_message = ["Job ID #{0} successfully canceled.".format(job_id)]

    return job_status(request, response={"result_messages": result_message, "error_message": error_message})
 
