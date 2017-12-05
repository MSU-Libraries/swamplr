# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from models import namespace_cache, namespace_operations, namespace_jobs, namespace_objects, object_results
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
from swamplr_jobs.views import add_job, job_status
from apps import SwamplrNamespacesConfig
from swamplr_jobs.models import status
from fedora_api.api import FedoraApi
import logging
import requests
from lxml import etree
from cache import build_cache
import subprocess


def load_namespaces(request, count=25, sort_field="count", direction="-", update_cache=True):
    """Load all namespaces from cache."""
    if update_cache:
        args = ["python", "/var/www/swamplr/swamplr_namespaces/cache.py", "/var/www/swamplr/swamplr.cfg"]
        s = subprocess.call(args)        
        logging.info(s)

    response = {
        "headings": ["Number", "Namespace", "Count", "Actions"]
    }

    sort = direction + sort_field
    namespace_objects = namespace_cache.objects.all().order_by(sort)
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

def run_process(current_job):

    namespace_job = namespace_jobs.objects.get(job_id=current_job)
    operation_type = namespace_job.operation_id.operation_name
    namespace_function = "run_" + operation_type.lower()
    if operation_type.lower() == "reindex":
        try:
            run_reindex(namespace_job.namespace, current_job)
            status_obj = status.objects.get(status="Success")
            message = ["Reindex completed."]
        except Exception as e:
            logging.error("Unable to complete reindex.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during reindex."]
    elif operation_type.lower() == "delete":
        try:
            run_delete(namespace_job.namespace, current_job)
            status_obj = status.objects.get(status="Success")
            message = ["Deletion completed."]
        except Exception as e:
            logging.error("Unable to complete deletion.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during deletion."]
    
    else:
        logging.info("Unable to find function for operation {0}".format(operation_type))
    
    result = (status_obj.status_id, message)
    return result

def set_namespace_info(ns):
    """Prepare namespace object with additional info for display."""
    ns.actions = set_actions(ns)

def get_nav_bar():
    """Set contents of navigation bar for current app."""

    nav = {"label": "Namespaces",
           "name": "namespaces",
          }
    return nav

def get_actions(job):
    """Required function: return actions to populate in job table."""
    actions = []
    return actions

def set_actions(ns):
    """Required function: return actions to populate in job table."""
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
    return [reindex, delete]

def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id

    try:
        # Get data about successes, skips, failures.
        result_display = "<span class='label label-success'>{0} Succeeded</span> <span class='label label-danger'>{1} Failed</span>"
        results = get_job_objects(job_id)
        result_message = result_display.format(results["status_count"]["Success"], results["status_count"]["Failed"])
        ns_job = namespace_jobs.objects.get(job_id=job.job_id)
        details = [
            ("Process ID", ns_job.operation_id),
            ("Namespace", ns_job.namespace),
            ("Objects Processed", len(results["objects"])),
        ]

        info = ["Process: {0} <br/>".format(ns_job.operation_id.operation_name),
                "Namespace: {0} <br/>".format(ns_job.namespace),
                result_message]

    except Exception as e:
        label = "Not Found"
        details = [("None", "No Info Found")]
        info = ["No info available."]
        print e.message

    return info, details

def list_items(request, ns, count=25):
    """List pids (and other data) for a given namespace."""
    logging.info("Listing items in {0} namespace.".format(ns))
    namespace_obj = namespace_cache.objects.get(namespace=ns)

    response = {"count": namespace_obj.count,
                "namespace": ns}

    pid_search_term = ns + ":*"
    api = FedoraApi()
    api.set_dynamic_param("maxResults", "1000")
    status, found = api.find_objects(pid_search_term, fields=["pid", "label", "creator", "description", "cDate", "mDate"
                                                      "date", "type"])
    if status in [200, 201]:
        found_objects = extract_data_from_xml(found)

        paginator = Paginator(found_objects, count)
        page = request.GET.get('page')
        try:
            result_list = paginator.page(page)

        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            result_list = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            result_list = paginator.page(paginator.num_pages)

    response["namespaces"] = result_list
    return render(request, 'swamplr_namespaces/namespace.html', response)

def extract_data_from_xml(xml):
    """Get data from xml for user display."""
    x = etree.fromstring(xml)
    items = []
    for record in x.iterfind(".//{http://www.fedora.info/definitions/1/0/types/}objectFields"):
        item = {}
        for child in record:
            tag = child.tag.split("}")[1]
            item[tag] = child.text
        items.append(item)
    return items


def delete(request, ns):
    """Add delete job to queue."""
    logging.info("Adding delete job for namespace: {0}".format(ns))

    new_job = add_job(SwamplrNamespacesConfig.name)
    ns_operation = namespace_operations.objects.get(operation_name="Delete")

    namespace_job = namespace_jobs.objects.create(
        job_id=new_job,
        namespace=ns,
        operation_id=ns_operation
    )

    return redirect(job_status)

def reindex(request, ns):
    logging.info("Adding reindex job for namespace: {0}".format(ns))

    new_job = add_job(SwamplrNamespacesConfig.name)
    ns_operation = namespace_operations.objects.get(operation_name="Reindex")

    namespace_job = namespace_jobs.objects.create(
        job_id=new_job,
        namespace=ns,
        operation_id=ns_operation
    )

    return redirect(job_status)

def run_delete(ns, current_job):
    pid_search_term = ns + ":*"
    api = FedoraApi(username=settings.GSEARCH_USER, password=settings.GSEARCH_PASSWORD)
    count = namespace_cache.objects.get(namespace=ns).count
    api.set_dynamic_param("maxResults", count)
    status, found = api.find_objects(pid_search_term)
    
    if status in [200, 201]:
        found_objects = extract_data_from_xml(found)

        for o in found_objects:
            response, output = api.purge_object(o["pid"])
            if response in [200, 201]:
                result = "Success"
            else:
                result = "Failure"
            result_id = object_results.objects.get(label=result)

            namespace_objects.objects.create(
                job_id=current_job,
                completed=timezone.now(),
                result_id=result_id,
                pid=o["pid"],
            )

def run_reindex(ns, current_job):
    """Reindex all pids within a given namespace."""
    pid_search_term = ns + ":*"
    api = FedoraApi()
    api.set_dynamic_param("maxResults", "1000")
    
    status, found = api.find_objects(pid_search_term)
    if status in [200, 201]:
        found_objects = extract_data_from_xml(found)

        for o in found_objects:
            response = send_reindex(o["pid"])
            if response.ok:
                result = "Success"
            else:
                result = "Failure"
            result_id = object_results.objects.get(label=result)

            namespace_objects.objects.create(
                job_id=current_job,
                completed=timezone.now(),
                result_id=result_id,
                pid=o["pid"],
            )

def send_reindex(pid):
    """Make call to gsearch to reindex pid."""
    gsearch_url_search = settings.GSEARCH_URL + "rest?operation=updateIndex&action=fromPid&value=" + pid
    logging.info("Reindexing pid: {0}".format(pid))
    response = requests.get(gsearch_url_search, auth=(settings.GSEARCH_USER, settings.GSEARCH_PASSWORD))

    return response

def get_job_objects(job_id):

    results = {
        "status_count": {
            "Success": 0,
            "Failed": 0,
        },
        "objects": []
    }

    objects = namespace_objects.objects.filter(job_id=job_id)
    for o in objects:
        object_data = {}
        object_data["completed"] = o.completed
        object_data["result_id"] = o.result_id
        object_data["result"] = o.result_id.label
        object_data["pid"] = o.pid
        results["objects"].append(object_data)
        if o.result_id.label == "Success":
            results["status_count"]["Success"] += 1
        else:
            results["status_count"]["Failed"] += 1

    return results
