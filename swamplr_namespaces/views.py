# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from models import namespace_cache, namespace_operations, namespace_jobs, namespace_objects, object_results, cache_job, object_ids
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


def load_namespaces(request, count=25, sort_field="count", direction="-", update_cache=True):
    """Load all namespaces from cache."""
    """
    if update_cache:
        user = SwamplrNamespacesConfig.run_as_user

        user_id = getpwnam(user).pw_uid
        os.setuid(user_id)

        args = ["python", "/var/www/swamplr/swamplr_namespaces/cache.py", "/var/www/swamplr/swamplr.cfg"]
        s = subprocess.call(args)        
        logging.info("Subprocess cache called")
        if s == 1:
             logging.error("Error refreshing namespace cache.")
        else:
             logging.info("Cache updated successfully.")
    """

    response = {
        "headings": ["Number", "Namespace", "Count", "Actions"]
    }
    if direction == "asc":
        direction = ""
    elif direction == "desc":
        direction = "-"
    sort = direction + sort_field
    
    namespace_objects = namespace_cache.objects.all().order_by(sort)
    paginator = Paginator(namespace_objects, count)
    page = request.GET.get('page')
    if page is None:
        page = 1
    response["count_inc"] = (int(page) - 1) * int(count)

    response["namespace_count"] = namespace_objects.count()
    total_objects = 0
    for o in namespace_objects:
        total_objects += int(o.count)
    response["object_count"] = total_objects
    last_cache = cache_job.objects.get().last_run
    response["updated"] = last_cache

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
            namespace_cache.objects.filter(namespace=namespace_job.namespace).delete()            

        except Exception as e:
            logging.error("Unable to complete deletion.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during deletion."]

    elif operation_type.lower() == "mint doi":
        try:
            run_mint_doi(namespace_job.namespace, current_job)
            status_obj = status.objects.get(status="Success")
            message = ["All objects processed."]
            namespace_cache.objects.filter(namespace=namespace_job.namespace).delete()

        except Exception as e:
            logging.error("Unable to complete process.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during process."]

    elif operation_type.lower() == "mint ark":
        try:
            run_mint_ark(namespace_job.namespace, current_job)
            status_obj = status.objects.get(status="Success")
            message = ["All objects processed."]
            namespace_cache.objects.filter(namespace=namespace_job.namespace).delete()

        except Exception as e:
            logging.error("Unable to complete process.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during process."]
    
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
         "class": "btn-primary",
         "args": ns.namespace
        }
    delete = {
         "method": "DELETE",
         "label": "Delete All",
         "action": "delete",
         "class": "btn-danger",
         "args": ns.namespace
        }
    add_doi = {
        "method": "POST",
        "label": "Mint DOIs",
        "action": "mint_doi",
        "class": "btn-success",
        "args": ns.namespace
    }
    add_ark = {
        "method": "POST",
        "label": "Mint ARKs",
        "action": "mint_ark",
        "class": "btn-success",
        "args": ns.namespace
    }
    return [reindex, add_doi, add_ark, delete]

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
            ("Process ID", ns_job.operation_id.operation_id),
            ("Namespace", ns_job.namespace),
            ("Objects Processed", len(results["objects"])),
        ]

        info = ["Process: {0} <br/>".format(ns_job.operation_id.operation_name),
                "Namespace: {0} <br/>".format(ns_job.namespace),
                result_message]

    except Exception as e:

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
    found_objects = api.find_all_objects(pid_search_term, fields=["pid", "label", "creator", "description", "cDate", "mDate"
                                                      "date", "type"])
    if len(found_objects) > 0:

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
    found_objects = api.find_all_objects(pid_search_term)
    logging.info("Found {0} objects to delete.".format(len(found_objects)))
    
    if len(found_objects) > 0:
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
    
    found_objects = api.find_all_objects(pid_search_term)
    logging.info("Found {0} objects to reindex.".format(len(found_objects)))
    if len(found_objects) > 0:
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

def mint_doi(request, namespace):
    """Mint DOI for object if one does not already exist."""
    return add_id_job(namespace, "DOI")


def mint_ark(request, namespace):
    """Mint ARK for object if one does not already exist."""
    return add_id_job(namespace, "ARK")

def add_id_job(ns, id_type):
    """Add job to queue."""
    logging.info("Adding {0} job for namespace: {1}".format(id_type, ns))

    new_job = add_job(SwamplrNamespacesConfig.name)
    if id_type.lower() == "doi":
        ns_operation = namespace_operations.objects.get(operation_name="Mint DOI")
    elif id_type.lower() == "ark":
        ns_operation = namespace_operations.objects.get(operation_name="Mint ARK")

    namespace_jobs.objects.create(
        job_id=new_job,
        namespace=ns,
        operation_id=ns_operation
    )
    return redirect(job_status)

def run_mint_doi(ns, current_job):
    """Check if DOI exists for pid and create DOI if not."""

    found_objects = get_matching_objects(ns)

    if len(found_objects) > 0:
        for o in found_objects:

            response = make_id(o, "doi")

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

def run_mint_ark(ns, current_job):
    """Check if ARK exists and create DOI."""

def get_matching_objects(ns):
    """Get all matching objects based on namespace search."""
    pid_search_term = ns + ":*"

    api = FedoraApi(username=settings.GSEARCH_USER, password=settings.GSEARCH_PASSWORD)
    count = namespace_cache.objects.get(namespace=ns).count
    api.set_dynamic_param("maxResults", count)

    found_objects = api.find_all_objects(pid_search_term)
    logging.info("Found {0} object(s) to process.".format(len(found_objects)))

    return found_objects

def make_id(obj, id_type):
    """Object in repository for which to process ID."""

    if not id_exists(obj["pid"], id_type):

        data = get_item_data(obj["pid"])
        if data:
            fetch_id()
            logging.info("Ready to fetch ID.")
            logging.info(data)
            status = 200
        else:
            logging.error("Unable to return data needed to mint DOI for object: {0}".format(obj["pid"]))
            status = -1
    else:
        logging.info("ID already exists for: {0}".format(obj["pid"]))

    return status

def get_item_data(pid, id_type):
    """Get metadata about item for DOI or ARK creation."""
    if id_type == "doi":
        data = get_doi_data(pid)
    elif id_type == "ark":
        data = get_ark_data(pid)
    else:
        data = None

    return data


def get_doi_data(pid):
    """Get data to send to EZID for given PID.

    Required Field
    with Value or MODS or DC mapping

    Creator/creatorName
    oai_dc:dc/dc:creator


    Title
    mods:mods/mods:titleInfo/mods:title[not(@type)]


    Publisher
    Michigan State University


    PublicationYear
    oai_dc:dc/dc:date


    Resource Type
    Text/Dissertation
    """
    api = FedoraApi(username=settings.FEDORA_USER, password=settings.FEDORA_PASSWORD)
    dc_status, dc = api.get_datastream_dissemination(pid, "DC")
    mods_status, mods = api.get_datastream_dissemination(pid, "MODS")

    if not(ds_status in [200, 201] and mods_status in [200, 201]):

        return None

    doi_data = {
        "datacite.publisher": "Michigan State University",
        "datacite.resourcetype": "Text/Dissertation",
        "datacite.creator": "; ".join(get_dc_element(dc, "//dc:creator")),
        "datacite.publicationyear": get_dc_element(dc, "//dc:date")[0][:4],
        "datacite.title": get_mods_xpath(mods, "//titleInfo/title[not(@type)")[0]
    }
    return doi_data


def get_ark_data(pid):
    """Get data to send to EZID for given PID.

        Who
        oai_dc:dc/dc:creator


        What
        mods:mods/mods:titleInfo/mods:title[not(@type)]


        When
        oai_dc:dc/dc:date
    """
    api = FedoraApi(username=settings.FEDORA_USER, password=settings.FEDORA_PASSWORD)
    dc_status, dc = api.get_datastream(pid, "DC", format="xml")
    mods_status, mods = api.get_datastream(pid, "MODS", format="xml")

    if not(ds_status in [200, 201] and mods_status in [200, 201]):

        return None

    ark_data = {

        "erc.who": "; ".join(get_dc_element(dc, "//dc:creator")),
        "erc.when": get_dc_element(dc, "//dc:date")[0],
        "erc.what": get_mods_xpath(mods, "//titleInfo/title[not(@type)")[0]
    }
    return ark_data

def get_dc_element(dc, xpath):
    """Use dc string and xpath to retrieve element content."""
    xml = etree.fromstring(dc)
    root = xml.getroot()
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    element = root.xpath(xpath, namespaces=ns)
    return [e.text for e in element]

def get_mods_element(mods, xpath):
    """Get MODS element using xpath."""
    xml = etree.fromstring(mods)
    root = xml.getroot()
    ns = {"mods": "http://www.loc.gov/mods/v3"}
    element = root.xpath(xpath, namespaces=ns)
    return [e.text for e in element]

def fetch_id(obj, id_type):
    pass

def id_exists(pid, id_type):
    """Check if ID of id_type exists for given pid."""
    id_exists = False
    pid_object = object_ids.objects.get(pid=pid)
    if pid_object and getattr(pid_object, id_type) is not None:
        id_exists = True
        logging.info("{0} already exists for object. Minted {1}".format(id_type.upper(),
                                                                        getattr(pid_object, id_type + "_minted")))
    return id_exists
