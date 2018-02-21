"""Generic collections class for others to inherit."""
from __future__ import print_function
from swamplr import settings
from swamplr_jobs.models import job_messages, status, jobs
from models import object_results, job_objects, datastreams
from django.utils import timezone
from lxml import etree
import os
import json
import logging
from hint import HintFiles
from ingest import Ingest


class CollectionIngest(object):

    """General collection-oriented methods."""

    def __init__(self):
        """Initiate ingest of collection.

        args:
            job_id (int): id of this ingest job.
        """
        self.datastreams = None

        self.id_prefix = ""
        self.root_dir = ""

        # Count outcomes for display to user.
        self.successful_objects = 0
        self.failed_objects = 0
        self.skipped_objects = 0

        self.job = {}
        self.collection = {}
        self.collection_defaults = {}
     
        # 'Compound' content models are those with hierarchical directory structures.
        # All items in subdirectories will be processed as 'children' of the main item directory.
        self.compound_content_models = ["compound", "newspaper_issue", "book"]
        self.simple_content_models = ["large_image", "pdf", "newspaper_page", "oral_histories", "audio"]

        self.pidcounter = 0
        self.deleted_pid = ""

        self.error_messages = []

    def start_ingest(self, ingest_job, datastreams, collection_configs, collection_defaults):
        """Initiate ingest according to parameters from job in database and settings in collections.json.

        """
        self.job = ingest_job
        self.datastreams = datastreams
        self.collection = collection_configs
        self.collection_defaults = collection_defaults
        
        logging.info("Initializing Ingest for Job {0}".format(ingest_job.job_id.job_id))
        job_messages.objects.create(
            job_id=ingest_job.job_id,
            created=timezone.now(),
            message="Initializing Ingest Job."
        )
        # Find root_dir (folder should end in '_root'
        self.root_dir = self.get_root_dir()
        
        # Check if selected dir might perchance be an object directory itself. If so, process that object directory only. 
        if any([f.endswith(".xml") for f in os.listdir(self.root_dir)]):
            logging.info("Found object dir at root: {0}".format(self.root_dir))

            full_path = self.root_dir
            
            if not any([ex in full_path for ex in self.collection["exclude_strings"]]):
                self.prepare(full_path, sequence=1)

        else:
            for i, dir_x in enumerate(self.get_sub_dirs(self.root_dir)):

                logging.info("Processing {0}".format(dir_x))

                # Check if job has been cancelled.
                failure_status = jobs.objects.get(job_id=self.job.job_id.job_id).status_id.failure 
                if failure_status == "manual":
                    break
                # Stop after processing specified number of items.
                if ((self.successful_objects + self.failed_objects) >= self.job.subset > 0):
                    break

                full_path = os.path.join(self.root_dir, dir_x)

                # Move to next item if this path is set out to be excluded.
                if any([ex in full_path for ex in self.collection["exclude_strings"]]):
                    continue

                self.prepare(full_path, sequence=i)

    def prepare(self, full_path, sequence=1):
        """Assign object type if possible, otherwise skip.

        args:
            full_path(str): path to object directory.
        kwargs:
            sequence(int): the position of this object within a sequence (used for some collection types).
        """
        self.assess(full_path)

        if self.object_type:

            logging.info("Now preparing for ingest: {0}".format(full_path))
            self.ingest(full_path, sequence=sequence)

        else:

            logging.error("Unable to process {0}".format(full_path))

    def ingest(self, path, child=False, parent_pid=None, sequence=None):
        """Begin ingest following check of repo for item.

        args:
            path(str): path to dir containing object(s) for upload.
        """

        compound = True if self.object_types[self.object_type]["content_model"] in self.compound_content_models else False

        in_object = Ingest(
            path, self.root_dir, self.job, self.collection, self.collection_defaults, self.datastreams,
            self.object_type, child=child, compound=compound, parent_pid=parent_pid, sequence=sequence
        )

        # Check 'prognosis' for value of 'ingest' or 'skip'.
        if in_object.prognosis == "ingest":

            # Main function for building/updating objects.
            in_object.create_object()

            # Check success and process accordingly.
            if in_object.result == "success":
                self.successful_objects += 1
            else:
                self.failed_objects += 1

            if compound:
                self.process_child_objects(path, in_object.pid)

        elif in_object.prognosis == "skip":

            self.skipped_objects += 1
            logging.info("Skipping object at {0}".format(path))
            
            result_object = object_results.objects.get(label="Skipped")
            for ds in self.datastreams:
                datastream_object = datastreams.objects.get(datastream_label=ds[0])
                job_objects.objects.create(
                    job_id=self.job.job_id,
                    created=timezone.now(),
                    obj_file=path + "/Not Applicable",
                    result_id=result_object,
                    pid=in_object.pid,
                    datastream_id=datastream_object,
            )

    def process_child_objects(self, path, parent_pid):
        """Check for sub-objects and process accordingly.

        args:
            path(str): parent object path.
            parent_pid(str): pid of parent object.
        """
        logging.info("Processing child objects")
        subdirs = self.get_sub_dirs(path)

        for index, s in enumerate(sorted(subdirs)):

            full_path = os.path.join(path, s)
            
            if any([ex in full_path for ex in self.collection["exclude_strings"]]):
                continue

            self.assess(full_path)

            if self.object_type:
                self.ingest(full_path, child=True, parent_pid=parent_pid, sequence=(index + 1))

            else:
                logging.error("Unable to process {0}".format(full_path))

    def assess(self, path):
        """Check which content model object seems to belong to.

        args:
            path(str): full path to directory to check.
        """
        # Get type as defined in hint files.
        # Hint file data takes precedence over all other indicators, as long as it exists in configs.
        hint = HintFiles(self.root_dir, path)
        hint_data = hint.get_hint_data()
        object_type = hint_data.get("type", "none")

        # Convenience variable: each object type as top-level key, includes all object configs.
        self.object_types = self.collection["objects"]

        # Confirm hint file type included in collection definition.
        content_models = {}
        for obj, values in self.object_types.items():
            content_models[values["content_model"]] = obj                

        if object_type in content_models.keys():
            self.object_type = content_models[object_type]

        # If no type defined in hint file, use collection configs.
        elif object_type == "none":
            self.assign_collection_type(path)

        # In the case that the hint file type doesn't match the collection definition.
        else:
            logging.warning("Object type in hint file ({0}) does not match collection definition.".format(object_type))
            logging.warning("Found only: {0}".format(self.object_types))
            logging.warning("Using type defined in collection.")
            self.assign_collection_type(path)

    def assign_collection_type(self, path):
        """Check collection definition for type to use in given directory.

        args:
            path(str): full path to directory to check.
        """

        type_count = len(self.object_types.keys())
        if type_count == 1:
            self.object_type = self.object_types.keys()[0]

        else:
            logging.info("More than 1 collection type found in configs.")
            self.guess_collection_type(path)

    def guess_collection_type(self, path):
        """Attempt simple guess of collection type to use.

        args:
            path(str): full path to directory to check.
        """
        subdirs = self.get_sub_dirs(path)

        # Check if there are subdirs *not* specified as excluded patterns.
        if len(subdirs) > 0 and any(s not in self.collection["exclude_strings"] for s in subdirs):
            self.assign_type("compound")

        else:
            self.assign_type("simple")

    def assign_type(self, oclass):
        """Check configs and assign type based on class: "simple" or "compound".

        args:
            oclass(str): class of object type to retrieve, "simple" or "compound".
        """
        object_definitions = {"simple": [],
                              "compound": []}
        for key, value in self.object_types.items():
            if value["content_model"] in self.compound_content_models:
                object_definitions["compound"].append(key)
            else:
                object_definitions["simple"].append(key)

        if len(object_definitions[oclass]) > 1:
            logging.error("Unable to process: Too many object types.")
            self.object_type = None

        elif len(object_definitions[oclass]) == 0:
            logging.error("Unable to process: Couldn't find valid object type.")
            self.object_type = None
        else:
            self.object_type = object_definitions[oclass][0]
            logging.info("Determined object type: %s" % self.object_type)

    def get_sub_dirs(self, path):
        """Check for subdirectories in path."""
        return [f for f in sorted(os.listdir(path)) if os.path.isdir(os.path.join(path, f))]

    def _load_configs(self, setting):
        """Load json data from settings."""
        config_path = getattr(settings, setting)
        with open(config_path) as configs:
            data = json.load(configs)
        return data

    def gather_files_back_up(self, file_ending=".xml"):
        """Gather files of suitable type to begin ingest.

        kwargs:
            file_ending(str): file ending of all files to be gathered.
        """
        fileset = []
        for root, dirs, files in os.walk(self.input_path):
            for f in files:
                if f.endswith(file_ending) and not f.startswith("."):
                    fileset.append(os.path.join(root, f))
        return fileset

    def _get_basename(self, path):
        """Return base file name without extension.

        args:
            path(str): full path to the item.
        returns:
            [basename](str): filename w/o extension
        """
        base_file = os.path.basename(path)
        return os.path.splitext(base_file)[0]

    def _count_files(self, file_ending, directory):
        """Count files of particular file ending in a given dir.

        args:
            file_ending(str): file ending to find files for
            directory(str): where to look
        """
        return len([f for f in os.listdir(directory) if f.endswith(file_ending)])

    def get_root_dir(self):
        """Find root directory, which should end in _root.

        args:
            path(str): path to files to tally
        """
        path = self.job.source_dir 
        root_dir = path
        if "_root" not in root_dir:
            for root, dirs, files in os.walk(path):
                for dirx in dirs:
                    if dirx.endswith("_root"):
                        root_dir = os.path.join(root, dirx)
                        break
        logging.info("Root dir set as: {0}".format(root_dir))
        return root_dir
