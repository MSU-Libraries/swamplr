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
from models import derivative_files, derivative_jobs, job_derivatives, derivative_results
from swamplr_jobs.views import add_job, job_status
from apps import SwamplrDerivativesConfig
from datetime import datetime
import logging
import sys
from derivatives import Derivatives

def get_nav_bar():
    """Set contents of navigation bar for current app."""
    nav = {"label": "Derivatives",
           "name": "derivatives",
           "manage": False}
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
        status_id = d.start_derivatives(derivative_job, derivative_settings)
        output = "Derivatives job complete."
    except Exception as e:
        output = "{0} on line {1} of {2}: {3}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e)
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

def get_command_list(config, source_type, option_key):
    """Get commands from config file."""
    commands = config.options(option_key)
    command_steps = sorted([int(c.split(".")[1]) for c in commands if c.startswith("step.") and c.endswith(".command")])
    
    command_list = []
    for c in command_steps:
        join_key = "step.{0}.join".format(c)
        join_value = "AND"
        if config.has_option(option_key, join_key):
            join_value = config.get(option_key, join_key)
        command_list.append((config.get(option_key, "step.{0}.command".format(c)), join_value.upper()))
    if len(command_list) == 0 and config.has_option(option_key, "command"):
        command_list.append((config.get(option_key, "command"), "AND"))
    return command_list

def get_derivative_settings(source_type):
    """Get the derivative types and settings for the specified source type."""

    config = get_configs()
    section = "source." + source_type.lower()
    options = config.get(section, "derive_options").split(",")
    
    derive_settings = []
    for opt in options:

        option_key = "derive."+source_type.lower()+"."+opt.lower()
        command_list = get_command_list(config, source_type, option_key)
        output_file = config.get(option_key, "output_file")
        derive = {"derivative_type": opt, "commands": command_list, "output_file": output_file}
        derive_settings.append(derive)

    return derive_settings


def get_configs():
    """Load derivative config file."""
    config = ConfigParser()
    path_to_configs = os.path.join(settings.BASE_DIR, "swamplr_derivatives/derive.cfg")
    config.readfp(open(path_to_configs))
    return config

def manage(request):
    """Load the JSON config to the page."""
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
            source_file_extension=item_type,
            brightness=clean["brightness_value"],
            contrast=clean["contrast_value"]
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

def get_derive_settings(item_type, derive_type):
    """Get values for specified configs.

    args:
        item_type (str): should be one of existing item types, e.g. tif, jpg, wav.
        derive_type (st): should be one of existing derivative types, e.g. jpeg_low, json, etc.
        settings (list): list of all specified settings to return.
    """
    settings = {}
    config = get_configs()
    section = "derive.{0}.{1}".format(item_type, derive_type)
    for s in config.options(section):
        settings[s] = config.get(section, s)
    return settings

def get_status_info(job):
    """Required function: return infor about current job for display."""
    job_id = job.job_id

    # Get data about successes, skips, failures.
    deriv_job = derivative_jobs.objects.get(job_id=job_id)
    job_derives = job_derivatives.objects.filter(derive_id=deriv_job)
    derive_types = ", ".join([j.derive_type for j in job_derives])

    result_display = "<span class='label label-success'>{0} Succeeded</span> <span class='label label-danger'>{1} Failed</span> <span class='label label-default'>{2} Skipped</span>"
    results = get_job_objects(job_id)
    result_message = result_display.format(results["status_count"]["Success"], results["status_count"]["Failure"], results["status_count"]["Skipped"])
    info = ["Filetype: {0} <br/>".format(deriv_job.source_file_extension), "Derivatives: {0} <br/>".format(derive_types),
            result_message]

    return info, []

def get_job_objects(job_id, job_type=None):
    """Gather all objects created by the given job, and count successes/failures/skips."""

    results = {
        "status_count": {
            "Success": 0,
            "Failure": 0,
            "Skipped":0,
        },
        "objects": [],
        "type": "derivatives"
    }
    cfile = None   # Current source file  we are looping on
    fail_id = derivative_results.objects.get(label="Failure").result_id
    
    # Get derivative job and source directory.
    djob = derivative_jobs.objects.get(job_id=job_id)
    source_dir = djob.source_dir

    # Get derivatives associated with the job and store in list.
    jderiv = job_derivatives.objects.filter(derive_id=djob)
    derive_types = {j.job_derive_id: j.derive_type for j in jderiv}

    # Get target files associated with derivative processing.
    dfiles = derivative_files.objects.filter(job_derive_id__in=jderiv).values().order_by("source_file")

    # Get all result types
    all_results_dc = derivative_results.objects.all().values()
    all_results = {r["result_id"]:r["label"] for r in all_results_dc}

    # Each source file is at the head of a set of sub-results containing individual derivative data.
    object_head = {"job_id": job_id, "subs": [], "path": None, "pid": "", "result": ""}
    
    for o in dfiles:
        if (cfile != o["source_file"]):
            if (cfile != None):
                results = update_results(object_head, results, fail_id)

            cfile = o["source_file"]
            object_head = {"job_id": job_id, "subs": [], "path": None, "pid": "", "result": ""}

        object_data = {}
        object_data["derive_type"] = derive_types[o["job_derive_id_id"]]
        object_data["file"] = os.path.basename(o["target_file"]) if o["target_file"] else "~"
        object_data["created"] = o["created"]
        object_data["result_id"] = o["result_id_id"]

        object_data["result"] = all_results[o["result_id_id"]]
        object_head["subs"].append(object_data)
        object_head["path"] = o["source_file"]

    results = update_results(object_head, results, fail_id)

    return results

def update_results(object_head, results, fail_id):
    """Update results object."""
    all_result_ids = [obj["result_id"] for obj in object_head["subs"]]
    if len(set(all_result_ids)) == 1:
        results["status_count"][object_head["subs"][0]["result"]] += 1
        object_head["result"] = object_head["subs"][0]["result"]
    elif any([r_id == fail_id for r_id in all_result_ids]):
        object_head["result"] = "Failure"
        results["status_count"]["Failure"] += 1
    elif len(set(all_result_ids)) > 0:
        object_head["result"] = "Success"
        results["status_count"]["Success"] += 1
    results["objects"].append(object_head)
    return results

def get_job_details(job):
    """Required function: return detailed info about given job for display."""
    job_id = job.job_id

    deriv_job = derivative_jobs.objects.get(job_id=job_id)

    details = [
        ("Derivatives ID", deriv_job.derive_id),
        ("Source Directory", deriv_job.source_dir),
        ("Replace Existing Derivatives", "Y" if deriv_job.replace_on_duplicate == "y" else "N"),
        ("Items To Process", deriv_job.subset if deriv_job.subset != 0 else "All"),
        ("Brightness", deriv_job.brightness),
        ("Contrast", deriv_job.contrast)
    ]

    dv_details = job_derivatives.objects.filter(derive_id=deriv_job)
    details.append(("Derivative Types", ", ".join([d.derive_type for d in dv_details])))

    return details

