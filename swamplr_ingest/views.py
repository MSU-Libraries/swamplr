from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from apps import SwamplrIngestConfig
from models import ingest_jobs, job_datastreams, datastreams, job_objects, object_results
from collection import CollectionIngest
from forms import IngestForm
from swamplr_jobs.views import add_job, job_status 
from datetime import datetime
import logging
import os
import json


def manage(request, response={}):
    """Manage existing services and add new ones."""
    response.update(load_manage_data())
    return render(request, 'swamplr_services/manage.html', response)


def run_process(current_job):
    """Run process from swamplr_jobs.views."""

    ingest_job = ingest_jobs.objects.get(job_id=current_job)

    datastreams = []
    for ds_id in job_datastreams.objects.filter(ingest_id=ingest_job):
        otype = ds_id.object_type
        ds = datastreams.objects.get(datastream_id=ds_id).datastream_label
        datastreams.append((ds, otype))
    
    try:
        c = CollectionIngest()
        c.start_ingest(ingest_job, datastreams)

    except Exception as e:
        output = e
        status_id = service_status.objects.get(status="Script error").service_status_id_id

    return (status_id, [output])


def add_ingest_job(request, collection_name):
   
    response = {"error_messages": [],
                "result_messages": [],
                "base_dir": SwamplrIngestConfig.ingest_paths,
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

        new_job = add_job(SwamplrIngestConfig.name)
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
        for ds, otype, dtype in all_datastreams:
            if ds not in existing_ds:
                is_object = "y" if dtype == "datastreams" else "" 
                new_ds = datastreams.objects.create(
                    datastream_label=ds,
                    is_object=is_object,
                )

            job_datastream = job_datastreams.objects.create(
                ingest_id=ingest_job,
                object_type=otype,
                datastream_id=datastreams.objects.get(datastream_label=ds),
            )
        message = "Successfully added {0} job: {1}".format(SwamplrIngestConfig.name, new_job.job_id)
        response["result_messages"].append(message)
    
    else:

        message = "Unable to add job: Missing or invalid form data."
        response["error_messages"].append(message)
        
    return job_status(request, response=response)


def run_ingest(request, collection_name):
   
    form = IngestForm()
    cname = get_ingest_data(collection_name)["label"]
    form.set_fields(collection_name)
    form.set_form_action(collection_name)
    response = {
        "form": form,
        "cname": cname,
        "base_dir": SwamplrIngestConfig.ingest_paths,
    }          
    return render(request, "swamplr_ingest/ingest.html", response)


def load_manage_data():
    """Load data for manage page."""
    service_objects = services.objects.all()
    all_services = []

    for s in service_objects:

        all_services.append(
            {
             "id": s.service_id,
             "label": s.label,
             "description": s.description,
             "command": s.command,
             "run_as_user": s.run_as_user,
             "frequency": s.frequency,
             "last_started": s.last_started,
            }
        )    

    form = ServicesForm()
    response = {
        "form": form,
        "services": all_services,
    }   
    return response

def get_status_info(job):
    """Required function: return info about current job for display."""
    job_id = job.job_id

    try:
        ingest_job = ingest_jobs.objects.get(job_id=job.job_id)
        ingest_data = get_ingest_data(ingest_job.collection_name)
        collection_label = ingest_data["label"]
        details = [
            ("Ingest ID", ingest_job.ingest_id),
            ("Collection Type", ingest_job.collection_name),
            ("Namespace", ingest_job.namespace),
            ("Process New Objects", ingest_job.process_new.upper()),
            ("Process Existing Objects", ingest_job.process_existing.upper()),
            ("Replace Duplicate Datastreams", ingest_job.replace_on_duplicate.upper()),
            ("Items To Process", ingest_job.subset if ingest_job.subset != 0 else "All"),
        ]
        ds_data = {}
        job_ds = job_datastreams.objects.filter(ingest_id=ingest_job.ingest_id)
        for j in job_ds:
            ds = datastreams.objects.get(datastream_id=j.datastream_id_id)
            label = ds.datastream_label
            ds_type = "Datastreams" if ds.is_object == "y" else "Metadata"
            object_type = j.object_type
            print ingest_data["objects"][object_type]
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

    # Cause of this exception would be the service being deleted from the table.
    except Exception as e:
        label = "Not Found"
        details = [("None", "No Info Found")]
        print e.message

    info = ["Namespace: {0} <br/>".format(ingest_job.namespace), "Collection: {0}".format(collection_label)]

    return info, details


def get_actions(job):
    """Required function: return actions to populate in job table."""
    actions = []
    return actions


def get_nav_bar():
    """Set contents of navigation bar for current app."""
    nav = {"label": "Ingest",
           "name": "ingest"}
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


def get_ingest_data(ingest_type):
    """Load ingest data and return values based on type.

    args:
        ingest_type(str): ingest type or collection name. Should match
            config key.
    """
    data = load_ingest_data()
    default = load_collection_defaults()
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
    

def get_all_metadata(collection_data, form_data):
    """Wrapper to get metadata types via get_all_datastreams function."""
    return get_all_datastreams(collection_data, form_data, value_type="metadata")


def get_all_datastreams(collection_data, form_data, value_type="datastreams"):
    """Transfer datastreams from form values to database ready values.

    args:
        collection_data(dict): data from json-configured collection configs.
        form_data(dict): data from collection upload form.
    kwargs:
        values(str): either 'datastreams' or 'metadata'; the type of user input to retrieve.
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

    return datastreams


def browse(request):
    """Return the list of directories  along with the parent directory as a json value."""
    data = []
    repo_directory = request.GET.get('selected_dir', None)
    navigateBack = True if request.GET.get('back') == 'true' else False
    base_dirs = []
    for path in SwamplrIngestConfig.ingest_paths:
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

