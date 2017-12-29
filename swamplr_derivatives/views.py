# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from ConfigParser import ConfigParser
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
import os
from forms import DerivativesForm
from django.shortcuts import render
from django.conf import settings
from swamplr_jobs.models import status
from models import derivative_jobs, job_derivatives
from swamplr_jobs.views import add_job, job_status
from apps import SwamplrDerivativesConfig
from datetime import datetime
import logging
from derivatives import Derivatives

def get_nav_bar():
    """Set contents of navigation bar for current app."""
    nav = {"label": "Derivatives",
           "name": "derivatives"}
    nav["children"] = get_derivative_options("source")
    return nav

def run_process(current_job):
    """Run process from swamplr_jobs.views."""
    
    # Get the job object
    derivative_job = derivative_jobs.objects.get(job_id=current_job)

    # Get the config settings for the job type
    derivative_settings = get_derivative_settings(derivative_job.source_file_extension)

    # kick off the ingest job and update the status
    try:
        d = Derivatives()
        d.start_derivatives(derivative_job, derivative_settings)
        status_id = status.objects.get(status="Success").status_id
        output = "Derivatives job complete."
    except Exception as e:
        output = e
        status_id = status.objects.get(status="Script error").status_id

    return (status_id, [output])

def get_derivative_options(section):
    """Check config file for options to include."""
    config = get_configs()
    options = config.get(section.lower(), "source_options").split(",")
    nav_options = []
    for o in options:
        nav_option = {
            "label": o,
            "id": o,
        }
        nav_options.append(nav_option)
    return nav_options

def get_derivative_settings(source_type):
    """Get the derivative types and settings for the specified source type."""

    config = get_configs()
    options = config.get("source."+source_type.lower(),"derive_options").split(",")
    derive_settings = []
    for opt in options:
        command = config.get("derive."+source_type.lower()+"."+opt.lower(),"command")
        output_file = config.get("derive."+source_type.lower()+"."+opt.lower(),"output_file")
        derive = {"derivative_type":opt, "command":command, "output_file":output_file}
        derive_settings.append(derive)
    return derive_settings


def get_configs():
    """Load derivative config file."""
    config = ConfigParser()
    path_to_configs = os.path.join(settings.BASE_DIR, "swamplr_derivatives/derive.cfg")
    config.readfp(open(path_to_configs))
    return config

def manage(request):
    """Load the JSON config to the pag."""
    # TODO
    pass

def run_derivatives(request, item_type, message=[]):
    
    form = DerivativesForm()
    form.set_form_action(item_type)
    form.set_fields(item_type)
    response = {
        "form": form,
        "item_type": item_type,
        "base_dir": settings.DATA_PATHS,
        "message": message 
    }          
    return render(request, "swamplr_derivatives/derive.html", response)
    

def add_derivatives_job(request, item_type):
    """Create a new job for the derivative form that was submitted"""

    response = {"error_messages": [],
                "result_messages": [],
                "base_dir": settings.DATA_PATHS,
    }

    #derive_options = get_derivative_options("source." + item_type.lower())

    form = DerivativesForm(request.POST)
    form.set_fields(item_type)

    if form.is_valid():
        clean = form.cleaned_data

        object_derivatives = clean["derive_types"]
        replace = "y" if clean["replace_on_duplicate"] else ""
        subset = int(clean["subset_value"]) if clean["subset_value"] else 0

        new_job = add_job(SwamplrDerivativesConfig.name)
        derivative_job = derivative_jobs.objects.create(
            job_id=new_job,
            source_dir=clean["path_list_selected"],
            replace_on_duplicate=replace,
            subset=subset,
            source_file_extension=item_type
        )

        for d in object_derivatives:
            new_derive = job_derivatives.objects.create(
                derive_id=derivative_job,
                derive_type=d,
                parameters="" # TODO -- populate
            )

    else:
        message = ["Unable to add job: Missing or invalid form data."]
        return run_derivatives(request, item_type, message=message)

    return redirect(job_status)


def browse(request):
    """Return the list of directories  along with the parent directory as a json value."""
    data = []
    repo_directory = request.GET.get('selected_dir', None)
    navigateBack = True if request.GET.get('back') == 'true' else False
    base_dirs = []
    for path in settings.DATA_PATHS:
        base_dirs.append(path)
        if path in repo_directory:
            base_path = path

    # check to see if the back button is pressed .
    if navigateBack:
        if repo_directory == base_path:
            isRoot = True
        else:
            parent = os.path.abspath(os.path.join(repo_directory, os.pardir))
            isRoot = False
            for child in os.listdir(parent):
                child_path = os.path.join(parent, child)
                if os.path.isdir(child_path):
                    data.append(child_path)
            # To associate the back button with the parent of the list.
            if parent == base_path:
                repo_directory = base_path
            else:
                repo_directory = parent
    else:
        # the selected directory is set as the parent while navigating forward.
        isRoot = False
        for child in os.listdir(repo_directory):
                child_path = os.path.join(repo_directory, child)
                if os.path.isdir(child_path):
                    data.append(child_path)

    data.sort()
    base_dirs.sort()
    return JsonResponse({'data': data, 'parent': repo_directory, "isRoot": isRoot, 'base_dirs': base_dirs})


def get_derive_data(item_type):
    config = get_configs()
    section = "source.{0}".format(item_type.lower())
    return config.get(section, "derive_options").split(",")
   
def get_status_info(job):
    """Required function: return infor about current job for display."""
    job_id = job.job_id

    try:
        result_display =  "<span class='label label-success'>{0} Succeeded</span> <span class='label label-danger'>{1} Failed</span> <span class='label label-default'>{2} Skipped</span>"

        # TODO
        label = "Not Found"
        details = [("None","No Info Found")]
        info = ["No info available."]
 
    except Exception as e:
        label = "Not Found"
        details = [("None","No Info Found")]
        info = ["No info available."]
        print e.message

    return info, details

def get_actions(job):
    """Required function: return actions to populate in job table."""
    actions = []
    return actions
 
