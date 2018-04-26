from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Count
from apps import SwamplrIngestConfig
from models import ingest_jobs, delete_jobs, delete_objects, job_datastreams, datastreams, job_objects, object_results, pathauto_jobs, pathauto_objects
from swamplr_jobs.models import status, job_types, jobs
from collection import CollectionIngest
from forms import IngestForm
from swamplr_jobs.views import add_job, job_status 
from datetime import datetime
from fedora_api.api import FedoraApi
import logging
import sys
import os
import json
from django.conf import settings
from django.db import connections

def manage(request):
    """Manage existing services and add new ones."""
    data = load_manage_data()
    return render(request, 'swamplr_ingest/manage.html', data)


def run_process(current_job):
    """Run process from swamplr_jobs.views."""

    result = None
    # First handle different job types.
    if current_job.type_id.label == "ingest":
        result = process_ingest(current_job)

    elif current_job.type_id.label == "delete":
        result = process_delete(current_job)

    elif current_job.type_id.label == "pathauto":
        result = process_pathauto(current_job)

    return result

def process_ingest(current_job):

    ingest_job = ingest_jobs.objects.get(job_id=current_job)
    collection_defaults = load_collection_defaults()
    collection_data = get_ingest_data(ingest_job.collection_name)

    user_datastreams = []
    for ds in job_datastreams.objects.filter(ingest_id=ingest_job):
        otype = ds.object_type
        user_datastreams.append((ds.datastream_id.datastream_label, otype))
    
    try:
        c = CollectionIngest()
        status_id = c.start_ingest(ingest_job, user_datastreams, collection_data, collection_defaults)
        output = "Ingest complete."

    except Exception as e:
        output = "{0} on line {1} of {2}: {3}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e)
        status_id = status.objects.get(status="Script error").status_id

    return (status_id, [output])

def process_pathauto(current_job):
    pathauto_job = pathauto_jobs.objects.get(job_id=current_job).source_job.job_id
    objects_to_generate = job_objects.objects.filter(job_id=pathauto_job)
    count = 0
    messages = []
    generated = []
    status_id = None

    try:
        for o in objects_to_generate:
            pid = o.pid
            if pid in generated or pid is None:
                continue
            else:
                generated.append(pid)
            # check if the job is still active (i.e. not cancelled by the user)
            failure_status = jobs.objects.get(job_id=current_job.job_id).status_id.failure
            if failure_status == "manual":
                messages.append("Job manually stopped by user.")
                status_id = status.objects.get(status="Cancelled By User").status_id
                break

            source = "islandora/object/{0}".format(pid)
            alias = "{0}/{1}".format(pid.split(":")[0], pid.split(":")[1])
            with connections['drupal'].cursor() as cursor:
                try:
                    cursor.execute("SELECT alias FROM url_alias WHERE source = %s",[source])
                    record = cursor.fetchone()
                    if record is not None and len(record) == 1:
                        logging.debug("Pauthauto URL already exists for PID: {0}".format(pid))
                    else:
                        logging.info("Creating Pathauto URL for PID: {0}. source: {1}. alias: {2}".format(pid, source, alias))
                        cursor.execute("INSERT INTO url_alias (source, alias, language) VALUES (%s, %s, 'und')", [source, alias])
                    result_id = object_results.objects.get(label="Success")
                except Exception as e:
                    result_id = object_results.objects.get(label="Failure")
                    messages.append("Could not create pathauto URL for {0}. Error: {1}".format(pid, e))
                finally:
                    # Insert into job objects table
                    pathauto_objects.objects.create(
                        job_id=current_job,
                        generated=timezone.now(),
                        result_id=result_id,
                        pid=pid,
                    )
        status_id = status.objects.get(status="Complete").status_id
  
    except Exception as e:
        messages.append("{0} on line {1} of {2}: {3}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e))
        status_id = status.objects.get(status="Script error").status_id

    return (status_id, messages)

def process_delete(current_job):

    delete_job = delete_jobs.objects.get(job_id=current_job).source_job.job_id
    objects_to_delete = job_objects.objects.filter(job_id=delete_job)
    count = 0
    deleted = []
    skipped = []
    try:
        for o in objects_to_delete:
            if o.new_object: 
                if o.pid not in deleted:
                    response = delete_object(current_job, o.pid)
                    deleted.append(o.pid)
                    if response in [200, 201]:
                        count += 1
                else:
                    pass
            else:
                if o.pid not in skipped:
                    result_id = object_results.objects.get(label="Skipped")

                    delete_objects.objects.create(
                        job_id=current_job,
                        deleted=timezone.now(),
                        result_id=result_id,
                        pid=o.pid,
                        )
                    skipped.append(o.pid)
                else:
                    pass

        status_id = status.objects.get(status="Complete").status_id
        output = "Deleted {0} object(s).".format(count)
    except Exception as e:
        output = "{0} on line {1} of {2}: {3}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e)
        status_id = status.objects.get(status="Script error").status_id

    return (status_id, [output])

def delete_object(current_job, pid):
    """Delete object by pid."""
    api = FedoraApi(username=settings.GSEARCH_USER, password=settings.GSEARCH_PASSWORD)
    response, output = api.purge_object(pid)
    if response in [200, 201]:
        result = "Success"
    else:
        result = "Failure"
    result_id = object_results.objects.get(label=result)

    delete_objects.objects.create(
        job_id=current_job,
        deleted=timezone.now(),
        result_id=result_id,
        pid=pid,
    )
    return response

def add_ingest_job(request, collection_name):
   
    response = {"error_messages": [],
                "result_messages": [],
                "base_dir": settings.DATA_PATHS,
    }

    collection_data = get_ingest_data(collection_name)

    form = IngestForm(request.POST)
    form.set_fields(collection_name)

    if form.is_valid():
    
        clean = form.cleaned_data
 
        object_datastreams = get_all_datastreams(collection_data, clean)
        metadata_datastreams = get_all_metadata(collection_data, clean)
        all_datastreams = object_datastreams + metadata_datastreams
    
        process_new = "y" if "process_new" in clean["process"] else ""
        process_existing = "y" if "process_existing" in clean["process"] else ""
        replace_on_duplicate = "y" if clean["replace_on_duplicate"] else ""
        subset = int(clean["subset_value"]) if clean["subset_value"] else 0

        new_job = add_job(SwamplrIngestConfig.name, job_type_label="ingest")
        ingest_job = ingest_jobs.objects.create(
            job_id=new_job,
            source_dir=clean["path_list_selected"],          
            replace_on_duplicate = replace_on_duplicate,
            collection_name=collection_name,
            namespace=clean["pid_namespace"],
            process_new=process_new,
            process_existing=process_existing,
            subset=subset,
        )
        ds_options = datastreams.objects.all()
        existing_ds = [ds.datastream_label for ds in ds_options]
        added = []
        for ds, otype, dtype in all_datastreams:
            if ds not in existing_ds and ds not in added:
                is_object = "y" if dtype == "datastreams" else "" 
                new_ds = datastreams.objects.create(
                    datastream_label=ds,
                    is_object=is_object,
                )
                added.append(ds)

            job_datastream = job_datastreams.objects.create(
                ingest_id=ingest_job,
                object_type=otype,
                datastream_id=datastreams.objects.get(datastream_label=ds),
            )
    
    else:

        message = ["Unable to add job: Missing or invalid form data."]
        return run_ingest(request, collection_name, message=message)
 
    return redirect(job_status)

def run_ingest(request, collection_name, message=[]):
   
    form = IngestForm()
    cname = get_ingest_data(collection_name)["label"]
    form.set_fields(collection_name)
    form.set_form_action(collection_name)
    response = {
        "form": form,
        "cname": cname,
        "base_dir": settings.DATA_PATHS,
        "message": message
    }          
    return render(request, "swamplr_ingest/ingest.html", response)


def load_manage_data():
    """Load data for manage page."""
    configs_path = SwamplrIngestConfig.collection_configs
    defaults_path = SwamplrIngestConfig.collection_defaults
    with open(configs_path) as f:
        configs = json.dumps(json.load(f), indent=4, separators=(',', ': '))
    with open(defaults_path) as f:
        defaults = json.dumps(json.load(f), indent=4, separators=(',', ': '))
    data = {
        "configs": configs,
        "defaults": defaults,
        "configs_path": configs_path,
        "defaults_path": defaults_path,
    }

    return data

def get_job_details(job):
    """Required function: return detailed info about given job for display."""
    job_id = job.job_id

    if job.type_id.label == "delete":
        delete_job = delete_jobs.objects.get(job_id=job_id)
        object_count = delete_objects.objects.filter(job_id=delete_job.job_id).annotate(Count('pid', distinct=True)).count()
        details = [
            ("Delete Job ID", delete_job.delete_id),
            ("Deleting New Items From Job", delete_job.source_job.job_id_id),
            ("Items Processed", object_count),
    ]
        
    elif job.type_id.label == "pathauto":
        pathauto_job = pathauto_jobs.objects.get(job_id=job_id)
        object_count = pathauto_objects.objects.filter(job_id=pathauto_job.job_id).annotate(Count('pid', distinct=True)).count()
        details = [
            ("Pathauto Job ID", pathauto_job.pathauto_job_id),
            ("Generating Pathauto URLs From Job", pathauto_job.source_job.job_id_id),
            ("Items Processed", object_count),
    ]


    elif job.type_id.label == "ingest":
        ingest_job = ingest_jobs.objects.get(job_id=job_id)
        ingest_data = get_ingest_data(ingest_job.collection_name)

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

    return details


def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id

    result_display = "<span class='label label-success'>{0} Succeeded</span> <span class='label label-danger'>{1} Failed</span> <span class='label label-default'>{2} Skipped</span>"
    info = [] 
    if job.type_id.label == "delete":
        delete_job = delete_jobs.objects.get(job_id=job_id)
        delete_id = delete_job.source_job.job_id_id
        info = ["Deleting From: <span class='job-data'>Job {0}</span> <br/>".format(delete_id)]

    elif job.type_id.label == "pathauto":
        pathauto_job = pathauto_jobs.objects.get(job_id=job_id)
        pathauto_id = pathauto_job.source_job.job_id_id
        info = ["Generating Pathauto For: <span class='job-data'>Job {0}</span> <br/>".format(pathauto_id)]
    elif job.type_id.label == "ingest":
        # Get data about successes, skips, failures.
        ingest_job = ingest_jobs.objects.get(job_id=job_id)
        ingest_data = get_ingest_data(ingest_job.collection_name)
        collection_label = ingest_data["label"]
        info = ["Namespace: {0} <br/>".format(ingest_job.namespace), "Collection: {0} <br/>".format(collection_label)]
    
    results = get_job_objects(job_id, job_type=job.type_id.label)
    result_message = result_display.format(results["status_count"]["Success"], results["status_count"]["Failure"], results["status_count"]["Skipped"])
    info.append(result_message) 

    return info, []

def get_actions(job):
    """Required function: return actions to populate in job table."""
    actions = []
    batch_delete = {
        "method": "DELETE",
        "label": "Delete Objects",
        "action": "delete-new",
        "class": "btn-danger",
        "args": str(job.job_id),
    }

    batch_pathauto = {
        "method": "PUT",
        "label": "Run Pathauto",
        "action": "pathauto-job",
        "class": "btn-success",
        "args": str(job.job_id),
    }

    stop_job = {
         "method": "POST",
         "label": "Stop Job",
         "action": "stop_job",
         "class": "btn-warning",
         "args": str(job.job_id)
        }
    rerun_job = {
        "method": "POST",
        "label": "Run same job",
        "action": "add_job",
        "class": "btn-info",
        "args": str(job.job_id),
        }

    archive_job = {
        "method": "POST",
        "label": "Remove Job",
        "action": "remove_job",
        "class": "btn-primary",
        "args": str(job.job_id)
    }

    if job.type_id.label == "ingest" and job.status_id.running != "y" and job.status_id.default != "y": 
        actions.append(batch_delete)
        actions.append(batch_pathauto)

    if job.status.default == "y" or job.status.running == "y":
        actions.append(stop_job)

    elif not job.archived:
        actions.append(archive_job)

    return actions

def add_delete_job(request, source_job_id):
    """Find all newly created objects associated with a given job."""
    new_job = add_job(SwamplrIngestConfig.name, job_type_label="delete")
    ingest_job = ingest_jobs.objects.get(job_id=source_job_id)

    delete_jobs.objects.create(
        job_id=new_job,
        source_job=ingest_job,
    )
    return redirect(job_status)

def add_pathauto_job(request, source_job_id):
    new_job = add_job(SwamplrIngestConfig.name, job_type_label="pathauto")
    ingest_job = ingest_jobs.objects.get(job_id=source_job_id)

    pathauto_jobs.objects.create(
        job_id=new_job,
        source_job=ingest_job,
    )
    return redirect(job_status)

def get_nav_bar():
    """Set contents of navigation bar for current app."""
    nav = {"label": "Ingest",
           "name": "ingest",
           "manage": True}
    nav["children"] = get_ingest_options()
    return nav

def get_ingest_options(status=["active"]):
    """Use configs to get options to use in ingest."""

    ingest_options = []

    data = load_ingest_data()

    for ingest_type, values in data.items():
        if values["status"] in status:
            d_settings = {
                "label": values["label"],
                "id": values["name"],
            }
            ingest_options.append(d_settings)

    return ingest_options

def get_job_objects(job_id, job_type="ingest"):
    results = {
        "status_count": {
            "Success": 0,
            "Failure": 0,
            "Skipped":0,
        },
        "objects": [],
        "type": job_type,
    }
    fail_id = object_results.objects.get(label="Failure").result_id
    success_id = object_results.objects.get(label="Success").result_id
    skip_id = object_results.objects.get(label="Skipped").result_id
    result_map = {
        fail_id: "Failure",
        success_id: "Success",
        skip_id: "Skipped",
    }

    if job_type == "delete":
        objects = delete_objects.objects.filter(job_id=job_id).values()
        for o in objects:
            object_data = {
                "completed": o["deleted"],
                "result_id": o["result_id_id"],
                "result": result_map[o["result_id_id"]],
                "pid": o["pid"],
        }
            results["objects"].append(object_data)

        results["status_count"]["Success"] = delete_objects.objects.filter(job_id=job_id, result_id=success_id).count()
        results["status_count"]["Skipped"] = delete_objects.objects.filter(job_id=job_id, result_id=skip_id).count()
        results["status_count"]["Failure"] = delete_objects.objects.filter(job_id=job_id, result_id=fail_id).count()
        return results

    if job_type == "pathauto":
        objects = pathauto_objects.objects.filter(job_id=job_id).values()
        for o in objects:
            object_data = {
                "generated": o["generated"],
                "result_id": o["result_id_id"],
                "result": result_map[o["result_id_id"]],
                "pid": o["pid"],
        }
            results["objects"].append(object_data)

        results["status_count"]["Success"] = pathauto_objects.objects.filter(job_id=job_id, result_id=success_id).count()
        results["status_count"]["Skipped"] = pathauto_objects.objects.filter(job_id=job_id, result_id=skip_id).count()
        results["status_count"]["Failure"] = pathauto_objects.objects.filter(job_id=job_id, result_id=fail_id).count()
        return results

    
    cpid = None   # Current pid we are looping on
    all_results_dc = object_results.objects.all().values()
    all_datastreams_dc = datastreams.objects.all().values()

    all_results = {r["result_id"]:r["label"] for r in all_results_dc}
    all_datastreams = {d["datastream_id"]: d["datastream_label"] for d in all_datastreams_dc}

    objects = job_objects.objects.filter(job_id=job_id).values().order_by('pid')
    object_head = {"job_id": job_id, "subs": [], "path": None, "pid": "", "result": ""}
    count = 0
    for o in objects:
        count += 1
        if (cpid != o["pid"]):
            if (cpid != None):
                results = update_results(object_head, results, fail_id)

            cpid = o["pid"] if ":" in o["pid"] else "[skipped object #{0}]".format(count)
            object_head = {"job_id": job_id, "subs": [], "path": None, "pid": "", "result": ""}
        
        object_data = {}
        object_data["datastream"] = all_datastreams[o["datastream_id_id"]]
        object_data["file"] = os.path.basename(o["obj_file"]) if o["obj_file"] else "Null"
        object_data["created"] = o["created"]
        object_data["result_id"] = o["result_id_id"]
        object_data["result"] = all_results[o["result_id_id"]]
        object_data["pid"] = cpid
        object_head["subs"].append(object_data)
        if object_head["path"] is None and o["obj_file"] is not None:
            object_head["path"] = "/".join(o["obj_file"].rstrip("/").split("/")[:-1])
        object_head["pid"] = cpid

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

def get_ingest_data(ingest_type):
    """Load ingest data and return values based on type.

    args:
        ingest_type(str): ingest type or collection name. Should match
            config key.
    """
    data = load_ingest_data()
    return data[ingest_type]

def load_ingest_data():
    """Load json file of collection data."""
    config_path = SwamplrIngestConfig.collection_configs
    with open(config_path) as configs:
        data = json.load(configs)
    return data

def load_collection_defaults():
    """Load json file of collection data."""
    default_path = SwamplrIngestConfig.collection_defaults
    with open(default_path) as configs:
        data = json.load(configs)
    return data

def get_all_metadata(collection_data, form_data):
    """Wrapper to get metadata types via get_all_datastreams function."""
    return get_all_datastreams(collection_data, form_data, value_type="metadata")


def get_all_datastreams(collection_data, form_data, value_type="datastreams"):
    """Transfer datastreams from form values to database ready values.

    args:
        collection_data(dict): data from json-configured collection configs.
        form_data(dict): data from collection upload form.
    kwargs:
        value_type(str): either 'datastreams' or 'metadata'; the type of user input to retrieve.
    """
    # list to be populated with 2-tuples of datastream name and object type
    # it's associated with.
    datastreams = []
    object_types = collection_data["objects"].keys()
    # For each type of object associated with the given collection.
    for otype in object_types:
        # This key structure is set in forms.py
        # The structure there will have to match the format here.
        key = "{0}-{1}".format(otype, value_type)
        ds_values = form_data[key]
        # For each checked box for each object type, add value and type.
        for ds_value in ds_values:
            datastreams.append((ds_value, otype, value_type))
        # Disabled "DC" form value does not get included in POST; re-adding DC here.
        if value_type == "metadata":
            datastreams.append(("DC", otype, "metadata"))
    return datastreams

def load_json(self, path):
    with open(path) as f:
        data = json.load(f)

    return data

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

