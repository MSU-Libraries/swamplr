# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from models import namespace_cache, namespace_operations, namespace_jobs, namespace_objects, object_results, cache_job, \
    object_ids
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
from swamplr_jobs.views import add_job, job_status
from apps import SwamplrNamespacesConfig
from swamplr_jobs.models import status, jobs
from fedora_api.api import FedoraApi
from ezid_api.api import Ezid
import logging
import os
from StringIO import StringIO
import requests
from lxml import etree
from rdflib.graph import Graph
from django.db import connections

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
    messages = [] # messages returned from operation functions
    message = [] # message set in run_process based on exceptions

    if operation_type.lower() == "reindex":
        try:
            messages, status_obj = run_reindex(namespace_job.namespace, current_job)
            message = ["Reindex completed."]
        except Exception as e:
            logging.error("Unable to complete reindex.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during reindex."]

    elif operation_type.lower() == "delete":
        try:
            messages, status_obj = run_delete(namespace_job.namespace, current_job)
            message = ["Deletion completed."]
            namespace_cache.objects.filter(namespace=namespace_job.namespace).delete()
        except Exception as e:
            logging.error("Unable to complete deletion.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during deletion."]

    elif operation_type.lower() in ["mint doi", "mint ark"]:
        try:
            messages, status_obj = run_mint_id(namespace_job.namespace, current_job, operation_type[-3:].lower())
            message = ["All objects processed",
                       "IDs may take up to 30 minutes to take effect, and may appear as invalid until then."]
        except Exception as e:
            logging.error("Unable to complete process.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during process."]
    elif operation_type.lower() == "pathauto":
        try:
            messages, status_obj = run_pathauto(namespace_job.namespace, current_job)
            message = ["Pathauto URL generation complete."]
        except Exception as e:
            logging.error("Unable to complete pathauto URL generation.")
            status_obj = status.objects.get(status="Script error")
            message = [e, "Error during pathauto URL generation."]
    else:
        logging.error("Unable to find function for operation {0}".format(operation_type))

    message = messages + message # merge all messages
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
        "args": ns.namespace,
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
    pathauto = {
        "method": "POST",
        "label": "Pathauto",
        "action": "pathauto",
        "class": "btn-primary",
        "args": ns.namespace
    }
    return [reindex, add_doi, add_ark, pathauto, delete]


def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id

    try:
        # Get data about successes, skips, failures.
        result_display = "<span class='label label-success'>{0} Succeeded</span> <span class='label label-danger'>{1} Failed</span>"
        results = get_job_counts(job_id)
        result_message = result_display.format(results["status_count"]["Success"], results["status_count"]["Failed"])
        ns_job = namespace_jobs.objects.get(job_id=job.job_id)

        if job.namespace_jobs.operation_id.operation_name in ["Mint DOI", "Mint ARK"]:
            result_display = "<span class='label label-success'>{0} Succeeded</span> <span class='label label-danger'>{1} Failed</span> <span class='label label-default'>{2} Skipped</span>"
            result_message = result_display.format(results["status_count"]["Success"],
                                                   results["status_count"]["Failed"],
                                                   results["status_count"]["Skipped"])

        info = ["Process: {0} <br/>".format(ns_job.operation_id.operation_name),
                "Namespace: {0} <br/>".format(ns_job.namespace),
                result_message]

    except Exception as e:

        info = ["No info available."]
        logging.error(e.message)

    return info, []


def get_job_details(job):
    ns_job = namespace_jobs.objects.get(job_id=job.job_id)
    objects = namespace_objects.objects.filter(job_id=job.job_id).values()

    details = [
        ("Process ID", ns_job.operation_id.operation_id),
        ("Process Name", ns_job.operation_id.operation_name),
        ("Namespace", ns_job.namespace),
        ("Objects Processed", len(objects)),
    ]
    return details


def list_items(request, ns, count=25):
    """List pids (and other data) for a given namespace."""
    logging.info("Listing items in {0} namespace.".format(ns))
    namespace_obj = namespace_cache.objects.get(namespace=ns)

    response = {"count": namespace_obj.count,
                "namespace": ns}

    pid_search_term = ns + ":*"
    api = FedoraApi()
    found_objects = api.find_all_objects(pid_search_term,
                                         fields=["pid", "label", "creator", "description", "cDate", "mDate"
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

    namespace_jobs.objects.create(
        job_id=new_job,
        namespace=ns,
        operation_id=ns_operation
    )

    return redirect(job_status)


def reindex(request, ns):
    if ns == "all":
        logging.info("Adding reindex job for all items.")
        ns = "[all items]"
    else:
        logging.info("Adding reindex job for namespace: {0}".format(ns))
    new_job = add_job(SwamplrNamespacesConfig.name)
    ns_operation = namespace_operations.objects.get(operation_name="Reindex")

    namespace_jobs.objects.create(
        job_id=new_job,
        namespace=ns,
        operation_id=ns_operation
    )

    return redirect(job_status)


def run_pathauto(ns, current_job):
    messages = []
    status_obj = None

    pid_search_term = ns + ":*"
    api = FedoraApi(username=settings.GSEARCH_USER, password=settings.GSEARCH_PASSWORD)
    count = namespace_cache.objects.get(namespace=ns).count
    api.set_dynamic_param("maxResults", count)
    found_objects = api.find_all_objects(pid_search_term)
    logging.info("Found {0} objects to generate pathauto URLs for.".format(len(found_objects)))

    if len(found_objects) > 0:
        for o in found_objects:
            pid = o['pid']
            # check if the job is still active (i.e. not cancelled by the user)
            failure_status = jobs.objects.get(job_id=current_job.job_id).status_id.failure
            if failure_status == "manual":
                messages.append("Job manually stopped by user.")
                status_obj = status.objects.get(status="Cancelled By User")
                break

            source = "islandora/object/{0}".format(pid)
            alias = "{0}/{1}".format(pid.split(":")[0], pid.split(":")[1]) 
            with connections['drupal'].cursor() as cursor:
                try:
                    cursor.execute("SELECT alias FROM url_alias WHERE source = %s",[source])
                    record = cursor.fetchone()
                    if record is not None and len(record) == 1:
                        messages.append("Pathauto URL already exists for PID: {0}".format(pid))
                        logging.info("Pathauto URL already exists for PID: {0}".format(pid))
                    else:
                        logging.info("Creating Pathauto URL for PID: {0}. source: {1}. alias: {2}".format(pid, source, alias))
                        cursor.execute("INSERT INTO url_alias (source, alias, language) VALUES (%s, %s, 'und')", [source, alias])
                    result_id = object_results.objects.get(label="Success")
                except Exception as e:
                    result_id = object_results.objects.get(label="Failure")
                    messages.append("Could not create pathauto URL for {0}. Error: {1}".format(pid, e))
                finally:
                    # Insert into job objects table
                    namespace_objects.objects.create(
                        job_id=current_job,
                        completed=timezone.now(),
                        result_id=result_id,
                        pid=pid,
                    )

    if status_obj is None:
        status_obj = status.objects.get(status="Complete")
    return messages, status_obj

def run_delete(ns, current_job):
    messages = []
    status_obj = None
    pid_search_term = ns + ":*"
    api = FedoraApi(username=settings.GSEARCH_USER, password=settings.GSEARCH_PASSWORD)
    count = namespace_cache.objects.get(namespace=ns).count
    api.set_dynamic_param("maxResults", count)
    found_objects = api.find_all_objects(pid_search_term)
    logging.info("Found {0} objects to delete.".format(len(found_objects)))

    if len(found_objects) > 0:
        for o in found_objects:
            # check if the job is still active (i.e. not cancelled by the user)
            failure_status = jobs.objects.get(job_id=current_job.job_id).status_id.failure 
            if failure_status == "manual":
                messages.append("Job manually stopped by user.")
                status_obj = status.objects.get(status="Cancelled By User")
                break

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
    if status_obj is None:
        status_obj = status.objects.get(status="Complete")
    return messages, status_obj

def run_reindex(ns, current_job):
    """Reindex all pids within a given namespace."""
    messages = []
    status_obj = None
    if ns.startswith("[") and ns.endswith("]"):
        pid_search_term = "*"
    else:
        pid_search_term = ns + ":*"

    api = FedoraApi()

    found_objects = api.find_all_objects(pid_search_term)
    logging.info("Found {0} objects to reindex.".format(len(found_objects)))
    if len(found_objects) > 0:
        for o in found_objects:
            # check if the job is still active (i.e. not cancelled by the user)
            failure_status = jobs.objects.get(job_id=current_job.job_id).status_id.failure 
            if failure_status == "manual":
                messages.append("Job manually stopped by user.")
                status_obj = status.objects.get(status="Cancelled By User")
                break
    
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

    if status_obj is None:
        status_obj = status.objects.get(status="Complete")
    return messages, status_obj

def send_reindex(pid):
    """Make call to gsearch to reindex pid."""
    gsearch_url_search = settings.GSEARCH_URL + "rest?operation=updateIndex&action=fromPid&value=" + pid
    logging.info("Reindexing pid: {0}".format(pid))
    response = requests.get(gsearch_url_search, auth=(settings.GSEARCH_USER, settings.GSEARCH_PASSWORD))

    return response


def get_job_objects(job_id, job_type=None):
    results = {
        "status_count": {
            "Success": 0,
            "Failed": 0,
            "Skipped": 0
        },
        "objects": []
    }

    objects = namespace_objects.objects.filter(job_id=job_id).values()
    pids = list(set([o["pid"] for o in objects]))
    o_pid_objects = {o["pid"]:o for o in object_ids.objects.filter(pid__in=pids).values()}

    operation_name = namespace_jobs.objects.get(job_id=job_id).operation_id.operation_name
    
    fail_id = object_results.objects.get(label="Failure").result_id
    success_id = object_results.objects.get(label="Success").result_id
    skip_id = object_results.objects.get(label="Skipped").result_id

    result_map = {
        fail_id: "Failure",
        success_id: "Success",
        skip_id: "Skipped",
    }

    for o in objects:
        object_data = {
            "completed": o["completed"],
            "result_id": o["result_id_id"],
            "result": result_map[o["result_id_id"]],
            "pid": o["pid"]
        }
        if operation_name in ["Mint DOI", "Mint ARK"]:
            uid = "N/A"
            created = None
            pid = o["pid"]
            if pid in pids and operation_name == "Mint DOI":
                if pid in o_pid_objects and o_pid_objects[pid]["doi"] is not None:
                    uid = "https://doi.org/{0}".format(o_pid_objects[pid]["doi"].split(":")[1])
                    created = o_pid_objects[pid]["doi_minted"]
            elif pid in pids and operation_name == "Mint ARK":
                if pid in o_pid_objects and o_pid_objects[pid]["ark"] is not None:
                    uid = "https://n2t.net/{0}".format(o_pid_objects[pid]["ark"])
                    created = o_pid_objects[pid]["ark_minted"]
            object_data["uid"] = uid
            object_data["created"] = created
        results["objects"].append(object_data)

    results["status_count"]["Success"] = namespace_objects.objects.filter(job_id=job_id, result_id=success_id).count()
    results["status_count"]["Skipped"] = namespace_objects.objects.filter(job_id=job_id, result_id=skip_id).count()
    results["status_count"]["Failed"] = namespace_objects.objects.filter(job_id=job_id, result_id=fail_id).count()

    return results


def get_job_counts(job_id):
    results = {
        "status_count": {
            "Success": 0,
            "Failed": 0,
            "Skipped": 0
        },
        "objects": []
    }

    fail_id = object_results.objects.get(label="Failure").result_id
    success_id = object_results.objects.get(label="Success").result_id
    skip_id = object_results.objects.get(label="Skipped").result_id

    results["status_count"]["Success"] = namespace_objects.objects.filter(job_id=job_id, result_id=success_id).count()
    results["status_count"]["Skipped"] = namespace_objects.objects.filter(job_id=job_id, result_id=skip_id).count()
    results["status_count"]["Failed"] = namespace_objects.objects.filter(job_id=job_id, result_id=fail_id).count()

    return results

def mint_doi(request, namespace):
    """Mint DOI for object if one does not already exist."""
    return add_id_job(namespace, "DOI")


def mint_ark(request, namespace):
    """Mint ARK for object if one does not already exist."""
    return add_id_job(namespace, "ARK")

def pathauto(request, namespace):
    """Generate the pathauto urls for all the items in the namespace"""
    return add_id_job(namespace,"Pathauto")

def add_id_job(ns, id_type):
    """Add job to queue."""
    logging.info("Adding {0} job for namespace: {1}".format(id_type, ns))

    new_job = add_job(SwamplrNamespacesConfig.name)
    if id_type.lower() == "doi":
        ns_operation = namespace_operations.objects.get(operation_name="Mint DOI")
    elif id_type.lower() == "ark":
        ns_operation = namespace_operations.objects.get(operation_name="Mint ARK")
    elif id_type.lower() == "pathauto":
        ns_operation = namespace_operations.objects.get(operation_name="Pathauto")

    namespace_jobs.objects.create(
        job_id=new_job,
        namespace=ns,
        operation_id=ns_operation
    )
    return redirect(job_status)


def load_excluded_pids():
    """Load file containing excluded pids. File should be located in same dir as views.py."""
    excluded_pids = []

    exclude_file_path = os.path.join(settings.BASE_DIR, "swamplr_namespaces", settings.EXCLUDE_LIST)

    if os.path.exists(exclude_file_path):
        with open(exclude_file_path, "rb") as f:
            excluded_pids = [a.strip() for a in f if not a.startswith("#")]

    return excluded_pids


def update_uid(uid, success):
    """Update status of uid depending on success.

     Delete uid if metadata couldn't be updated.
     Change status of uid -- mark as not reserved -- if successfully added to metadata.
     """
    ez = Ezid(username=settings.EZID_USER, password=settings.EZID_PASSWORD)

    if success:
        result = "Success"
        ez.modify(uid, {"_status": "public"})
    else:
        result = "Failure"
        ez.delete(uid)

    return result


def run_mint_id(ns, current_job, id_type):
    """Mint ID of given type."""
    # Find all objects matching namespace.
    found_objects = get_matching_objects(ns)

    messages = []
    status_obj = None

    if len(found_objects) > 0:
        for o in found_objects:
            # check if the job is still active (i.e. not cancelled by the user)
            failure_status = jobs.objects.get(job_id=current_job.job_id).status_id.failure 
            if failure_status == "manual":
                messages.append("Job manually stopped by user.")
                status_obj = status.objects.get(status="Cancelled By User")
                break

            response, uid, message = make_id(o, id_type)
            if message is not None:
                messages.append(message)

            # Make url version of id.
            if uid and id_type == "doi":

                uid_url = "https://doi.org/{0}".format(uid.split(":")[1])

            elif uid and id_type == "ark":

                uid_url = "https://n2t.net/{0}".format(uid)

            else:
                uid_url = None

            # If creation of id was successful, add to metadata and update.
            if response in [200, 201]:

                uid_added = add_uid_to_metadata(o["pid"], uid, uid_url, id_type)
                result = update_uid(uid, uid_added)

            # Response code of -2 indicates a skip.
            # If uid exists, then this is presumably from a previous attempt; clarify this logic here.
            elif response == -2 and uid is not None:
                uid_added = add_uid_to_metadata(o["pid"], uid, uid_url, id_type)
                result = update_uid(uid, uid_added)

            elif response == -2 and uid is None:
                result = "Skipped"

            else:
                result = "Failure"

            result_id = object_results.objects.get(label=result)

            namespace_objects.objects.create(
                job_id=current_job,
                completed=timezone.now(),
                result_id=result_id,
                pid=o["pid"],
            )

    if status_obj is None:
        status_obj = status.objects.get(status="Complete")
    return messages, status_obj


def add_uid_to_metadata(pid, uid, url, id_type):
    """Update MODS and DC datastreams with url form of ID."""
    success = False
    mods_success = add_uid_to_mods(pid, url, id_type)
    dc_success = add_uid_to_dc(pid, url, id_type)
    if mods_success and dc_success:
        success = True

        if object_ids.objects.filter(pid=pid).exists():
            id_object = object_ids.objects.get(pid=pid)
        else:
            id_object = object_ids.objects.create(
                pid=pid,
            )
        setattr(id_object, id_type, uid)
        setattr(id_object, "{0}_minted".format(id_type), timezone.now())
        id_object.save()

    return success


def add_uid_to_mods(pid, url, id_type):
    """Grab MODS datastream and update to include id url."""
    success = False

    status, mods = get_xml_datastream(pid, "MODS")

    if status in [200, 201]:

        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(mods, parser)

        mods_ns = "http://www.loc.gov/mods/v3"
        nsmap = {"mods": mods_ns}

        xpath = "/mods:mods/mods:location/mods:url[@note='{0}']".format(id_type)
        id_urls = tree.xpath(xpath, namespaces=nsmap)

        # Remove existing IDs.
        for u in id_urls:
            parent = u.getparent()
            parent.getparent().remove(parent)

        location_tag = "{{{0}}}location".format(mods_ns)
        location_element = etree.Element(location_tag, nsmap=nsmap)

        url_tag = "{{{0}}}url".format(mods_ns)
        url_element = etree.SubElement(location_element, url_tag, nsmap=nsmap,
                                       usage="primary", note=id_type)
        url_element.text = url

        tree.insert(-1, location_element)
        api = FedoraApi(username=settings.FEDORA_USER, password=settings.FEDORA_PASSWORD)
        status, response = api.update_datastream_content(
            pid,
            "MODS",
            StringIO(etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8")),
            mimeType="text/xml"
        )
        if status in [200, 201]:
            success = True
            logging.info("Updated MODS metadata")
        else:
            logging.error("Unable to update MODS metadata.")

    else:
        logging.warning("Unable to access MODS datastream for: {0}".format(pid))

    return success


def add_uid_to_dc(pid, url, id_type):
    """Get DC datastream and update with id url."""
    success = False

    status, dc = get_xml_datastream(pid, "DC")

    if status in [200, 201]:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(dc, parser)

        dc_ns = "http://purl.org/dc/elements/1.1/"
        dc_id_tag = "{{{0}}}identifier".format(dc_ns)
        nsmap = {"dc": dc_ns}

        xpath = "//dc:identifier"
        id_urls = tree.xpath(xpath, namespaces=nsmap)

        # Remove existing IDs that match ark or doi patterns.
        url_patterns = {
            "doi": "https://doi.org/",
            "ark": "https://n2t.net/"
        }
        for u in id_urls:
            if u.text and u.text.startswith(url_patterns[id_type]):
                u.getparent().remove(u)

        new_id_element = etree.SubElement(tree, dc_id_tag, nsmap=nsmap)
        new_id_element.text = url
        api = FedoraApi(username=settings.FEDORA_USER, password=settings.FEDORA_PASSWORD)
        status, response = api.update_datastream_content(
            pid,
            "DC",
            StringIO(etree.tostring(tree, pretty_print=True, encoding="UTF-8", xml_declaration=True)),
            mimeType="text/xml"
        )

        if status in [200, 201]:
            success = True
            logging.info("Updated DC metadata")
        else:
            logging.error("Unable to update DC metadata.")

    else:
        logging.warning("Unable to access DC datastream for: {0}".format(pid))

    return success


def get_xml_datastream(pid, datastream):
    """Get datastream content.

    Returns tuple of status and datastream content.
    """
    api = FedoraApi(username=settings.FEDORA_USER, password=settings.FEDORA_PASSWORD)
    return api.get_datastream_dissemination(pid, datastream)


def get_matching_objects(ns):
    """Get all matching objects based on namespace search."""
    pid_search_term = ns + ":*"

    api = FedoraApi(username=settings.FEDORA_USER, password=settings.FEDORA_PASSWORD)
    count = namespace_cache.objects.filter(namespace=ns).count
    api.set_dynamic_param("maxResults", count)

    found_objects = api.find_all_objects(pid_search_term)
    logging.info("Found {0} object(s) to process.".format(len(found_objects)))

    return found_objects


def make_id(obj, id_type):
    """Object in repository for which to process ID."""
    status = -2
    uid = None
    message = None
    pid = obj["pid"]
    logging.info("Now processing pid: {0}".format(pid))

    excluded_pids = load_excluded_pids()

    if child_or_root_object(pid):
        # Check if pid is a root object or child object. If so, skip.
        logging.info("Object at {0} appears to be a child or root object. Skipping.".format(pid))

    elif pid in excluded_pids:
        # Check if pid has been blacklisted.
        logging.info(
            "Object at {0} appears to be on the list of excluded PIDs ({1}).".format(pid, settings.EXCLUDE_LIST))

    elif not id_exists(pid, id_type.lower()):

        data = get_item_data(pid, id_type)

        if data:
            logging.info("Ready to fetch ID.")
            status, uid = fetch_id(obj, id_type, data)

        else:
            logging.error("Unable to return data needed to mint {1} for object: {0}".format(obj["pid"], id_type))
            status = -1
    else:
        pid_object = object_ids.objects.get(pid=pid)
        uid = getattr(pid_object, id_type)
        logging.info("ID already exists for: {0}. Validating".format(pid))

        if not validate_existing_id(uid, id_type):
            ## Decided to let this fail instead of creating a new one in case the
            ## site was just down at the time we checked resulting in multiple IDs for the
            ## same pid. The process will now be to review the failures and manually update the 
            ## DB removing it's doi/ark record if we really want to re-create it.

            #data = get_item_data(pid, id_type)
            #logging.warning("ID is invalid. Minting new one.")
            #status, uid = fetch_id(obj, id_type, data)

            logging.error("ID '{0}' is invalid. Manually review and remove from the DB if it should be regenerated".format(uid))
            message = "ID '{0}' is invalid for pid {1}. Manually review and remove from the DB if it should be regenerated".format(uid, pid)
            status = -1

        else:
            logging.info("Validation successful.")

    if status in [200, 201]:
        logging.info("Successfully created {0} for {1}: {2}".format(
            id_type.upper(),
            obj["pid"],
            uid
        ))

    elif status == -1:
        logging.error("Failed to create {0} for {1}".format(
            id_type.upper(),
            pid
        ))

    return status, uid, message


def child_or_root_object(pid):
    """Check if pid represents a child or root object and skip if so.

    3 steps to check if pid should be excluded as a root or child object:
        1. if pid ends with :root
        2. if object has a disallowed content model, e.g. newspaper page or collection.
        3. if object has the "isConstituentOf" predicate.

    """
    child_or_root = False
    if pid.endswith(":root"):
        child_or_root = True
        return child_or_root

    disallowed_cms = [
        "info:fedora/islandora:newspaperCModel",
        "info:fedora/islandora:newspaperPageCModel",
        "info:fedora/islandora:collectionCModel"
    ]
    api = FedoraApi(username=settings.FEDORA_USER, password=settings.FEDORA_PASSWORD)

    status, object_profile = api.get_object_profile(pid=pid)
    cmodels = get_content_models(object_profile)

    if any(c in disallowed_cms for c in cmodels):
        child_or_root = True
        return child_or_root

    status, rels_ext = api.get_relationships(pid)
    predicates = get_predicate_strings(rels_ext)
    if "info:fedora/fedora-system:def/relations-external#isConstituentOf" in predicates:
        child_or_root = True

    return child_or_root


def get_content_models(object_profile):
    """Get content models from object profile xml."""
    tree = etree.fromstring(object_profile)
    ns = {"f": "http://www.fedora.info/definitions/1/0/access/"}
    models = tree.xpath("//f:objModels/f:model", namespaces=ns)
    return [m.text for m in models]


def get_predicate_strings(rels_ext, format="nt"):
    """Extract string representations of predicates."""
    pred = get_predicates(rels_ext, format=format)
    return [str(p) for p in pred]


def get_predicates(rels_ext, format="nt"):
    """Return all predicates in a given rels_ext datastream."""
    g = Graph()
    content = g.parse(data=rels_ext, format=format)
    return list(content.predicates())


def validate_existing_id(uid, id_type):
    """Check existing uid to make sure it still resolves."""
    valid = True

    if id_type == "ark":
        uid_url = "https://n2t.net/{0}".format(uid)
    elif id_type == "doi":
        uid_url = "https://doi.org/{0}".format(uid.split(":")[1])

    r = requests.get(uid_url)

    if not r.ok or "lib.msu.edu" not in r.url:
        logging.info(r.url)
        valid = False

    return valid


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

    if not (dc_status in [200, 201] and mods_status in [200, 201]):
        return None

    who = "; ".join(get_dc_element(dc, "//dc:creator"))
    if who == "":
        who = "Creator not identified"

    doi_data = {
        "datacite.publisher": "Michigan State University",
        "datacite.resourcetype": "Text/Dissertation",
        "datacite.creator": who,
        "datacite.publicationyear": get_dc_element(dc, "//dc:date")[0],
        "datacite.title": get_mods_element(mods, "/mods:mods/mods:titleInfo/mods:title[not(@type)]")[0]
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
    dc_status, dc = api.get_datastream_dissemination(pid, "DC", format="xml")
    mods_status, mods = api.get_datastream_dissemination(pid, "MODS", format="xml")

    # Make sure DC and MODS datastreams are both available -- if not, do not create ID.
    if not (dc_status in [200, 201] and mods_status in [200, 201]):
        return None

    who = "; ".join(get_dc_element(dc, "//dc:creator"))
    if who == "":
        who = "Creator not identified"

    ark_data = {

        "erc.who": who,
        "erc.when": get_dc_element(dc, "//dc:date")[0][:4],
        "erc.what": get_mods_element(mods, "/mods:mods/mods:titleInfo/mods:title[not(@type)]")[0]
    }
    return ark_data


def get_dc_element(dc, xpath):
    """Use dc string and xpath to retrieve element content."""
    xml = etree.fromstring(dc)
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    element = xml.xpath(xpath, namespaces=ns)
    return [e.text for e in element]


def get_mods_element(mods, xpath):
    """Get MODS element using xpath."""
    xml = etree.fromstring(mods)
    ns = {"mods": "http://www.loc.gov/mods/v3"}
    element = xml.xpath(xpath, namespaces=ns)
    return [e.text for e in element]


def fetch_id(obj, id_type, data):
    """Communicate with EZID API to mint DOI/ARK."""
    shoulder = None

    if id_type == "ark":
        shoulder = settings.ARK_SHOULDER
    elif id_type == "doi":
        shoulder = settings.DOI_SHOULDER

    if shoulder:

        target_url = os.path.join(settings.REPO_URL, obj["pid"].replace(":", "/"))
        data["_target"] = target_url
        data["_status"] = "reserved"

        ez = Ezid(username=settings.EZID_USER, password=settings.EZID_PASSWORD)
        status, uid_result = ez.mint(shoulder, metadata=data)

        if status != -1:
            uid = uid_result.split("|")[0].split(": ")[1].strip()
        else:
            logging.info("Returned error fetching id: {0}".format(uid_result))
            uid = None
    else:
        status = -1
        uid = None

    return status, uid


def id_exists(pid, id_type):
    """Check if ID of id_type exists for given pid."""
    id_exists = False

    if object_ids.objects.filter(pid=pid).exists():
        pid_object = object_ids.objects.get(pid=pid)
    else:
        pid_object = None

    if pid_object and getattr(pid_object, id_type) is not None:
        id_exists = True
        logging.info("{0} already exists for object. Minted {1}".format(id_type.upper(),
                                                                        getattr(pid_object, id_type + "_minted")))
    return id_exists
