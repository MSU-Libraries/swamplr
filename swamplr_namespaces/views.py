# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from models import namespace_cache, namespace_operations, namespace_jobs
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect
from swamplr_jobs.views import add_job, job_status
from apps import SwamplrNamespacesConfig
from fedora_api.api import FedoraApi
import logging
from lxml import etree

def load_namespaces(request, count=25, sort_field="count", direction="-"):
    """Load all namespaces from cache."""
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
    return [list_items, reindex, delete]

def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id

    try:
        # Get data about successes, skips, failures.
        result_display = "<span class='label label-success'>{0} Succeeded</span> <span class='label label-danger'>{1} Failed</span> <span class='label label-default'>{2} Skipped</span>"
        results = get_job_objects(job_id)
        result_message = result_display.format(results["status_count"]["Success"], results["status_count"]["Failed"], results["status_count"]["Skipped"])
        ingest_job = ingest_jobs.objects.get(job_id=job.job_id)
        ingest_data = get_ingest_data(ingest_job.collection_name)
        collection_label = ingest_data["label"]
        details = [
            ("Ingest ID", ingest_job.ingest_id),
            ("Collection Type", ingest_job.collection_name),
            ("Namespace", ingest_job.namespace),
            ("Source Directory", ingest_job.source_dir),
            ("Process New Objects", "Y" if ingest_job.process_new == "y" else "N"),
            ("Process Existing Objects", "Y" if ingest_job.process_existing == "y" else "N"),
            ("Replace Duplicate Datastreams", "Y" if ingest_job.replace_on_duplicate == "y" else "N"),
            ("Items To Process", ingest_job.subset if ingest_job.subset != 0 else "All"),
        ]
        ds_data = {}
        job_ds = job_datastreams.objects.filter(ingest_id=ingest_job.ingest_id)
        for j in job_ds:
            ds = datastreams.objects.get(datastream_id=j.datastream_id_id)
            label = ds.datastream_label
            ds_type = "Datastreams" if ds.is_object == "y" else "Metadata"
            object_type = j.object_type
            if "label" in ingest_data["objects"][object_type]:
                object_type_label = ingest_data["objects"][object_type]["label"]
            else:
                object_type_label = object_type
            key = " ".join([object_type_label.capitalize(), ds_type])
            if key not in ds_data:
                ds_data[key] = [label]
            else:
                ds_data[key].append(label)
        for k, v in ds_data.items():
            details.append((k, ", ".join(v)))

        info = ["Namespace: {0} <br/>".format(ingest_job.namespace), "Collection: {0} <br/>".format(collection_label),
                result_message]


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

def extract_data_from_xml(self, xml):
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

def get_job_objects(job_id):

    results = {
        "status_count": {
            "Success": 0,
            "Failed": 0,
            "Skipped":0,
        },
        "objects": []
    }

    objects = job_objects.objects.filter(job_id=job_id)
    for o in objects:
        object_data = {}
        object_data["completed"] = o.completed
        object_data["result_id"] = o.result_id
        object_data["result"] = o.result_id.label
        object_data["pid"] = o.pid
        results["objects"].append(object_data)

    return results
