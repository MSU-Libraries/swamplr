from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from jobs import JobQueue
import importlib


APPS = [app for app in settings.INSTALLED_APPS if app.startswith("swamplr_")]

import_apps = {}


def jobs(request):
    """Populate data on current jobs on the Job Status page """
    jobs = JobQueue.get_jobs()
    return render(request, 'swamplr_jobs/jobs.html', {'jobs': jobs})

def main(request):
    """Landing page."""
    main = {}
    return render(request, 'swamplr_jobs/main.html', main)

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
