# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from ConfigParser import ConfigParser
from django.http import HttpResponse, JsonResponse
import os
from forms import DerivativesForm
from django.shortcuts import render
from django.conf import settings

def get_nav_bar():
    """Set contents of navigation bar for current app."""
    nav = {"label": "Derivatives",
           "name": "derivatives"}
    nav["children"] = get_derivative_options("source")
    return nav

def get_derivative_options(section):
    """Check config file for options to include."""
    config = get_configs()
    options = config.get(section, "source_options").split(",")
    nav_options = []
    for o in options:
        nav_option = {
            "label": o,
            "id": o,
        }
        nav_options.append(nav_option)
    return nav_options

def get_configs():
    """Load derivative config file."""
    config = ConfigParser()
    path_to_configs = os.path.join(settings.BASE_DIR, "swamplr_derivatives/derive.cfg")
    config.readfp(open(path_to_configs))
    return config

def manage(request):
    pass

def run_derivatives(request, item_type):
    
    form = DerivativesForm()
    form.set_form_action(item_type)
    form.set_fields(item_type)
    response = {
        "form": form,
        "item_type": item_type,
        "base_dir": settings.DATA_PATHS,
    }          
    return render(request, "swamplr_derivatives/derive.html", response)
    

def add_derivatives_job(request):
    pass

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
    
