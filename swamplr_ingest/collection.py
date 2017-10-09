"""Generic collections class for others to inherit."""
from __future__ import print_function
from swamplr import settings
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
     
        # 'Compound' content models are those with hierarchical directory structures.
        self.compound_content_models = ["compound", "newspaper_issue", "book"]
        self.simple_content_models = ["large_image", "pdf", "newspaper_page", "oral_histories", "audio"]

        self.pidcounter = 0
        self.deleted_pid = ""

        self.error_messages = []

        logging.info("Initializing Ingest for Job {0}".format(job_id))

    def start_ingest(self, ingest_job, datastreams, collection_configs):
        """Initiate ingest according to parameters from job in database and settings in collections.json.

        """
        self.job = ingest_job
        self.datastreams = datastreams
        self.collection = collection_configs

        # Find root_dir (folder should end in '_root'
        self.root_dir = self.get_root_dir()
        
        # Check if selected dir might perchance be an object directory itself. If so, process that object directory only. 
        if any([f.endswith(".xml") for f in os.listdir(self.root_dir)]):
            logging.info("Found object dir at root: {0}".format(self.root_dir))

            full_path = self.root_dir
            
            if not any([ex in full_path for ex in self.collection["exclude_strings"]]):
                self._prepare(full_path, sequence=1)

        else:
            for i, dir_x in enumerate(self.get_sub_dirs(self.root_dir)):

                logging.info("Checking {0}".format(dir_x))

                # Stop after processing specified number of items.
                if ((self.successful_objects + self.failed_objects) >= self.job.subset_value > 0):
                    break

                full_path = os.path.join(self.root_dir, dir_x)

                # Move to next item if this path is set out to be excluded.
                if any([ex in full_path for ex in self.collection["exclude_strings"]]):
                    continue

                self._prepare(full_path, sequence=i)

    def _prepare(self, full_path, sequence=1):
        """Assign object type if possible, otherwise skip.

        args:
            full_path(str): path to object directory.
        kwargs:
            sequence(int): the position of this object within a sequence (used for some collection types).
        """
        self._assess_object_directory(full_path)

        if self.object_type:

            logging.info("Now preparing for ingest: {0}".format(full_path))
            self._ingest(full_path, sequence=sequence)

        else:

            logging.error("Unable to process {0}".format(full_path))

    def _ingest(self, path, child=False, parent_pid=None, sequence=None):
        """Begin ingest following check of repo for item.

        args:
            path(str): path to dir containing object(s) for upload.
        """

        compound = True if self._object_types[self.object_type]["content_model"] in self.compound_content_models else False

        iobject = Ingest(path, self.job, self.collection, self.datastreams, 
                    self.object_type, child=child, compound=compound, 
                    parent_pid=parent_pid, sequence=sequence)

        # Check 'prognosis' for value of 'ingest' or 'skip'.
        if iobject.prognosis == "ingest":

            # Main function for building/updating objects.
            iobject.create_object()

            # Check success and process accordingly.
            if iobject.result == "success":
                self.successful_objects += 1

            else:
                self.failed_objects += 1

            if compound:
                self._process_child_objects(path, in_object.pid)

        elif in_object.prognosis == "skip":

            self.skipped_objects += 1
            JobQueue.insert_job_objects(self.job_id, path, "skipped")
            logging.info("Skipping object at {0}".format(path))

    def _process_child_objects(self, path, parent_pid):
        """Check for sub-objects and process accordingly.

        args:
            path(str): parent object path.
            parent_pid(str): pid of parent object.
        """
        logging.info("Processing child objects")
        subdirs = self.get_sub_dirs(path)
        for index, s in enumerate(sorted(subdirs)):

            full_path = os.path.join(path, s)
            
            if any([ex in full_path for ex in self._exlude_strings]):
                continue

            self._assess_object_directory(full_path)

            if self.object_type:
                self._process_for_ingest(full_path, child=True, parent_pid=parent_pid, sequence=(index + 1))

            else:
                logging.error("Unable to process {0}".format(full_path))

    def _load_job_data(self):
        """Load pertinent job data from database."""
        subset = int(self._ingest_job.subset)
        self.job_data = {
            "path_to_upload": self._ingest_job.source_dir,
            "replace": self._ingest_job.replace,
            "collection_name": self._ingest_job.collection_name,
            "namespace": self._ingest_job.namespace,
            "subset": subset
        }

    def _get_ingest_data(self, ingest_config):
        """Load ingest data and return values based on type.

        args:
            ingest_config(str): ingest type or collection name. Should match
                config key.
        """
        data = self._load_configs("COLLECTION_CONFIGS")
        return data[ingest_config]

    def _assess_object_directory(self, path):
        """Check which content model object seems to belong to.

        args:
            path(str): full path to directory to check.
        """
        # Get type as defined in hint files.
        hint = HintFiles(self._root_dir, path)
        hint_data = hint.get_hint_data()
        object_type = hint_data.get("type", "none")

        # Confirm hint file type included in collection definition.
        content_models = {}
        for obj, values in self._object_types.items():
            content_models[values["content_model"]] = obj                

        if object_type in content_models.keys():
            self.object_type = content_models[object_type]

        # If no type defined in hint file, use collection configs.
        elif object_type == "none":
            self._assign_collection_type(path)

        # In the case that the hint file type doesn't match the collection definition.
        else:
            logging.warning("Object type in hint file ({0}) does not match collection definition.".format(object_type))
            logging.warning("Found only: {0}".format(self._object_types))
            logging.warning("Using type defined in collection.")
            self._assign_collection_type(path)

    def _assign_collection_type(self, path):
        """Check collection definition for type to use in given directory.

        args:
            path(str): full path to directory to check.
        """

        type_count = len(self._object_types.keys())
        if type_count == 1:
            self.object_type = self._object_types.keys()[0]

        else:
            logging.info("More than 1 collection type found in configs.")
            self._guess_collection_type(path)

    def _guess_collection_type(self, path):
        """Attempt simple guess of collection type to use.

        args:
            path(str): full path to directory to check.
        """
        subdirs = self.get_sub_dirs(path)

        # Check if there are subdirs *not* specified as excluded patterns.
        if len(subdirs) > 0 and any(s not in self._exlude_strings for s in subdirs):
            self._assign_type("compound")

        else:
            self._assign_type("simple")

    def _assign_type(self, oclass):
        """Check configs and assign type based on class: "simple" or "compound".

        args:
            oclass(str): class of object type to retrieve, "simple" or "compound".
        """
        object_definitions = {"simple": [],
                              "compound": []}
        for key, value in self._object_types.items():
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

    def get_next_pid(self, namespace):
        """Get next pid in namespace."""
        response = self.api.getNextPID(namespace=namespace)
        return self._extract_pid(response.content)

    def _extract_pid(self, xml):
        """Extract pid from xml string.

        args:
            xml(str): xml content in string.
        """
        tree = etree.fromstring(xml)
        return tree.getchildren()[0].text

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

    def get_root_dir():
        """Find root directory, which should end in _root.

        args:
            path(str): path to files to tally
        """
        path = self.job.source_dir 
        root_dir = path
        for root, dirs, files in os.walk(path):
            for dirx in dirs:
                if dirx.endswith("_root"):
                    root_dir = os.path.join(root, dirx)
                    break

        return root_dir

