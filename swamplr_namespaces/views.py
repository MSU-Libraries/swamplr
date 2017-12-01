# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from models import namespace_cache, namespace_operations, namespace_jobs
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from swamplr_jobs.views import add_job, job_status
from apps import SwamplrNamespacesConfig
import logging


def load_namespaces(request, count=25):
    """Load all namespaces from cache."""
    response = {
        "headings": ["Number", "Namespace", "Count", "Actions"]
    }

    namespace_objects = namespace_cache.objects.all().order_by('-count')
    paginator = Paginator(namespace_objects, count)
    page = request.GET.get('page')

    try:
        namespace_list = paginator.page(page)

    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        namespace_list = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        namespace_list = paginator.page(paginator.num_pages)

    for ns in namespace_list.object_list:

        set_namespace_info(ns)

    response["namespaces"] = namespace_list

    return render(request, 'swamplr_namespaces/namespaces.html', response)

def set_namespace_info(ns):
    """Prepare namespace object with additional info for display."""
    ns.actions = get_actions(ns)

def get_nav_bar():
    """Set contents of navigation bar for current app."""

    nav = {"label": "Namespaces",
           "name": "namespaces",
          }
    return nav

def get_actions(ns):
    """Required function: return actions to populate in job table."""
    list_items = {
         "method": "POST",
         "label": "List Items",
         "action": "list_items",
         "class": "btn-success",
         "args": ns.namespace
        }
    reindex = {
         "method": "POST",
         "label": "Reindex",
         "action": "reindex",
         "class": "btn-success",
         "args": ns.namespace
        }
    delete = {
         "method": "DELETE",
         "label": "Delete All",
         "action": "delete",
         "class": "btn-danger",
         "args": ns.namespace
        }
    return [list_items, reindex, delete]


def reindex(request, ns):
    logging.info("Adding reindex job for namespace: {0}".format(ns))

    new_job = add_job(SwamplrNamespacesConfig.name)
    ns_operation = namespace_operations.objects.get(namespace_operation="Reindex")

    namespace_job = namespace_jobs.objects.create(
        job_id=new_job,
        namespace=ns,
        operation_id=ns_operation
    )

    return redirect(job_status)


def list_items(ns):
    pass
def delete(ns):
    pass
