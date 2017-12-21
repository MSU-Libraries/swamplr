# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from ConfigParser import ConfigParser
from django.shortcuts import render

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
            "name": o,
        }
        nav_options.append(nav_option)
    return nav_options

def get_configs():
    """Load derivative config file."""
    config = ConfigParser()
    config.readfp(open("derive.cfg"))
    return config

def manage(request):
    pass

def run_derivatives(request):
    pass

def add_derivatives_job(request):
    pass

def browse(request):
    pass
