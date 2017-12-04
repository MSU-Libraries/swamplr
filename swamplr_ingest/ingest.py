"""Ingest code for Large Image objects."""
import logging
import hashlib
from lxml import etree
from apps import SwamplrIngestConfig
from upload import Upload, LocalObject
from rdflib.namespace import Namespace
from fedora_api.api import FedoraApi
from swamplr import settings
from models import datastreams, job_objects, object_results
from swamplr_jobs.models import job_messages
from hint import HintFiles
from operator import itemgetter
from ConfigParser import ConfigParser
from django.utils import timezone
import os
import re
from rdflib.graph import Graph
from rdflib.term import URIRef


class Ingest:

    """Process ingest of collection to Fedora Commons."""

    def __init__(self, path, ingest_job, collection, defaults, datastreams, object_type,
                 compound=False, child=False, parent_pid=None, sequence=None):
        """Prepare for ingest."""
        # Path to object directory (containing datastream files).
        self.path = path

        # Assessed type of object, e.g. compound, large_image, pdf, etc.
        self.object_type = object_type

        # All job details from database.
        self.ingest_job = ingest_job
        self.namespace = self.ingest_job.namespace

        # All collection configs for the given collection name.
        self.collection = collection
        self.objects = collection["objects"]
        self.content_model = self.collection["objects"][object_type]["content_model"]

        # Default configs.
        self.defaults = defaults

        self.compound = compound
        self.child = child
        self.parent_pid = parent_pid
        self.sequence = sequence

        # List of datastreams as 2-tuple (name, associated object type).
        self.datastreams = datastreams
        logging.info("datastreams {0}".format(datastreams))
        # Future title.
        self.title = ""

        # Hint data.
        self.root_dir = self.get_root_dir()
        hint = HintFiles(self.root_dir, path)
        self.hint_data = hint.get_hint_data()

        # Pid progress.
        self.pids = None
        self.pid = None

        # Outlook and outcome.
        self.prognosis = "skip"
        self.result = "failed"

        # True if a new object is being created, false if one already exists.
        self.new_object = False
        self.current_ds_list = []

        # Just datastreams at the current layer, e.g. compound parent objects.
        self.object_datastreams = []

        # Extract and separate file datastreams from metadata according to current object layer.
        self.file_datastreams, self.metadata_datastreams = self.set_datastreams()
        # Dictionary containing datastream id as key, path to file as value.
        self.datastream_paths = self.gather_paths()
        # Connect to Fedora API
        self.fedora_api = self.connect_to_fedora()
       
        self.check_for_existing_object()

    def connect_to_fedora(self):
        """Use credentials to establish class for making API calls."""
        configs = ConfigParser()
        # Load configs preserving case
        configs.optionxform = str
        # Individual configs accessed via configs object.
        configs.readfp(open(SwamplrIngestConfig.fedora_config_path))

        username = configs.get("fedora", "username")
        password = configs.get("fedora", "password")

        return FedoraApi(username=username, password=password)

    def create_object(self):
        """Create object for upload, whether a new object or amended."""
        status = 201
        response = self.pid
 
        if not self.new_object:
            self.current_ds_list = self.get_current_datastreams()

        # Title is pulled from Dublin Core, and used as FC label.
        self.title = self.get_title(self.datastream_paths.get("DC", None))

        logging.info(u"Processing object at {0}: {1}".format(self.pid, self.title))

        if self.new_object: 
            status, response = self.fedora_api.ingest_at_pid(
                self.pid, label=self.title, ownerId="MSUL", logMessage="New object created at {0}".format(self.pid)
            )

        if status == 201 and response == self.pid:
            # Add rels-ext, metadata, files, then check outcome.
            self.add_rels_ext()
            self.add_metadata()
            self.add_files()
            if self.object_exists:
                self.result = "success"

        else:
            logging.info("Error ingesting object at PID: {0}. Error: {1}: {2}".format(self.pid, status, response))

    def get_current_datastreams(self):
        """Retrieve current datastreams for given object."""
        status, xml = self.fedora_api.list_datastreams(self.pid)
        ds_list = []
        tree = etree.fromstring(xml)
        dss = tree.xpath("//f:datastream", namespaces={"f":"http://www.fedora.info/definitions/1/0/access/"})
        for d in dss:
            ds_list.append(d.get("dsid"))
        return ds_list

    def add_rels_ext(self):
        """Add basic rels-ext for object."""

        # Load default settings for content model.
        has_model_object = self.defaults["content_models"][self.content_model]["has_model"]

        # Root pid, e.g. "etd:root" made by joining namespace and "root".
        root_pid = ":".join([self.pid.split(":")[0], "root"])

        logging.info("Adding relationships at {0}".format(self.pid))

        self.fedora_api.add_relationship(self.pid, "info:fedora/fedora-system:def/model#hasModel", has_model_object)

        if self.content_model == "newspaper_issue":
            self.fedora_api.add_relationship(
                self.pid, "info:fedora/fedora-system:def/relations-external#isMemberOf",
                "info:fedora/{0}".format(root_pid.replace("root", "1"))
            )
            self.fedora_api.add_relationship(
                self.pid, "http://islandora.ca/ontology/relsext#isSequenceNumber", self.sequence, isLiteral=True, datatype="int"
            )
            self.fedora_api.add_relationship(
                self.pid, "http://islandora.ca/ontology/relsext#dateIssued",
                self.get_date(self.datastream_paths.get("DC", None)), isLiteral=True
            )

        elif self.child:

            if self.content_model == "newspaper_page":
                self.fedora_api.add_relationship(
                    self.pid, "http://islandora.ca/ontology/relsext#isSequenceNumber", self.sequence, isLiteral="true",
                    datatype="int"
                )
                self.fedora_api.add_relationship(
                    self.pid, "http://islandora.ca/ontology/relsext#isPageNumber", self.sequence, isLiteral="true",
                    datatype="int"
                )
                self.fedora_api.add_relationship(
                    self.pid, "http://islandora.ca/ontology/relsext#isPageOf", "info:fedora/{0}".format(self.parent_pid)
                )
                self.fedora_api.add_relationship(
                    self.pid, "info:fedora/fedora-system:def/relations-external#isMemberOf",
                    "info:fedora/{0}".format(self.parent_pid)
                )
                new_title = "{0} Page {1}".format(self.title, self.sequence)
                self.fedora_api.modify_object(self.pid, label=new_title, logMessage="Update newspaper title")

            else:
                # Child object is 'constituent of' parent.
                self.fedora_api.add_relationship(
                    self.pid, "info:fedora/fedora-system:def/relations-external#isConstituentOf",
                    "info:fedora/{0}".format(self.parent_pid))

                sequence_predicate = self.set_sequence_predicate()
                self.fedora_api.add_relationship(self.pid, sequence_predicate, self.sequence, isLiteral="true", datatype="int")
                self.fedora_api.add_relationship(
                    self.pid, "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
                    "info:fedora/{0}".format(root_pid)
                )

        else:

            self.fedora_api.add_relationship(
                self.pid, "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
                "info:fedora/{0}".format(root_pid)
            )

        if self.hint_data.get("sequence", "false") == "true":
 
            # Set values for sequence name and sequence value.
            self.process_dir_sequence()
            self.fedora_api.add_relationship(
                self.pid, "http://islandora.ca/ontology/relsext#isSequenceNumber", self.sequence_value,
                isLiteral="true", datatype="int"
            )
            self.fedora_api.add_relationship(
                self.pid, "http://islandora.ca/ontology/relsext#isSequenceOf", self.sequence_term,
                isLiteral="true"
            )

    def process_dir_sequence(self):
        """Use sequence settings in hint file to assign appropriate sequence RELS-EXT."""
        
        # Regex pattern to match and use for sorting.
        pattern = self.hint_data["sequence_match"]
      
        # Remove trailing slash.
        object_path = self.normalize_path()

        # The sort directory is the root directory plus a number of steps down.
        path_length = len(self.root_dir.split("/")) + self.hint_data["sort_level"]

        # Divide and re-combine path of appropriate depth.
        sort_path_parts = object_path.split("/")[:path_length]

        # sort_path is the directory *containing* the elements that should be sorted.
        sort_path = "/" + os.path.join(*sort_path_parts)

        # object_leaf is the sortable element for the given object and settings.
        object_leaf = object_path.split("/")[path_length]

        filter_key = self.hint_data["filter_by"]
        sort_key = self.hint_data["sort_by"]

        filter_term, sort_value = self.get_matches(pattern, object_leaf, filter_key, sort_key)

        filtered = []

        for sub in [f for f in sorted(os.listdir(sort_path)) if os.path.isdir(os.path.join(sort_path, f))]:

            current_object = False
            subterm, subkey = self.get_matches(pattern, sub, filter_key, sort_key)

            if sub == object_leaf:
                current_object = True

            if subterm == filter_term:
                filtered.append((subterm, float(subkey), current_object))
        
        self.set_sequence_values(filtered)

    def set_sequence_values(self, slist):

        sort_order = self.hint_data["sort_direction"]
        slist.sort(key=itemgetter(1), reverse=(sort_order=="desc"))
        for index, values in enumerate(slist):
            if values[2]:
                self.sequence_value = index + 1
                self.sequence_term = values[0]

    def get_matches(self, pattern, text, *keys):
        """Get named matches from string."""
        values = []
        match = re.match(pattern, text)
        for key in keys:
            if key in match.groupdict():
                values.append(match.group(key))
            else:
                values.append(None)

        return values

    def normalize_path(self):
        """Remove trailing slash."""
        path = self.path
        if self.path.endswith("/"):
            path = path[:-1]
        return path

    def get_root_dir(self):
        """Get dirpath that ends in '*:root'."""
        root_dir = JobQueue.get_root_dir(self.path)
        path_sub_dirs = root_dir.rsplit("/")[1:]
        dirs = []
        for p in path_sub_dirs:
            dirs.append(p)
            if "_root" in p:
                break
        return "/" + os.path.join(*dirs)

    def set_sequence_predicate(self):
        """Set up predicate to record/check sequence number of child object."""
        if self.content_model == "newspaper_page":
            predicate = "http://islandora.ca/ontology/relsext#isSequenceNumber"
        else:
            # Sequence predicate for compound object children.
            pid_underscore = self.parent_pid.replace(":", "_")
            predicate = "http://islandora.ca/ontology/relsext#isSequenceNumberOf{0}".format(pid_underscore)
        return predicate

    def add_metadata(self):
        """Add metadata datastreams."""
        logging.info("Adding metadata at {0}".format(self.pid))
        for ds in self.metadata_datastreams:

            path = self.datastream_paths.get(ds, None)
            if not path:
                self.update_job_objects(path, ds, status="Skipped")
                logging.info("Missing datastream path for '{0}'".format(ds))
                continue
        
            name = os.path.splitext(os.path.basename(path))[0]
            label = self.set_ds_label(ds, name)

            # 3 ways to move forward with adding datastream:
            # The object is new to the repository, the object is not new, but the datastream should be replaced,
            # or the object is not new and the datastream doesn't yet exist.
            if ((self.new_object and self.ingest_job.process_new == 'y') or (ds not in self.current_ds_list and self.ingest_job.process_existing == 'y'))\
                and ds in self.datastream_paths:

                status, result = self.fedora_api.add_datastream(
                    self.pid, ds, path,
                    dsLabel=label,
                    mimeType=self.get_datastream_value(ds, "mimetype"),
                    logMessage="Adding DS: {0} to PID: {1}".format(ds, self.pid)
                )

            elif self.ingest_job.replace_on_duplicate == 'y' and ds in self.datastream_paths:

                status, result = self.fedora_api.add_datastream(
                    self.pid, ds,
                    filepath=path,
                    dsLabel=label,
                    mimeType=self.get_datastream_value(ds, "mimetype"),
                    logMessage="Adding DS: {0} to PID: {1}".format(ds, self.pid)
                )

            else:
                status = 200
                logging.info("Not updating or creating datastream: {0} for PID: {1}".format(ds, self.pid))

            if status not in [200, 201]:
                self.update_job_objects(path, ds, status="Success")
                logging.info("Failed to add or modify datastream: {0} for pid: {1} with error {2}: {3}".format(ds, self.pid, status, result))
            else:
                self.update_job_objects(path, ds)
        """
        if self.child:
            # For child objects, establish additional unique ID that combines generic ID and sequence number.
            object_id = self.get_identifier(self.datastream_paths["DC"])
            child_object_id = "{0}-{1}".format(object_id, "{:03d}".format(int(self.sequence)))

            self.object_upload.set_dc_ident_attr(child_object_id)
        """
    def get_datastream_value(self, ds, key):
        """Check default configs and use unless overwritten in collection settings."""
        if ds in self.defaults["datastreams"]:
            t = "datastreams"
            default = self.defaults["datastreams"][ds].get(key, None)
        elif ds in self.defaults["metadata"]:
            t = "metadata"
            default = self.defaults["metadata"][ds].get(key, None)

        return self.collection["objects"][self.object_type][t][ds].get(key, default)

    def add_files(self):
        """Create file datastreams for large image objects."""
        logging.info("Adding objects at {0}".format(self.pid))

        for ds in self.file_datastreams:
            path = self.datastream_paths.get(ds, None)
            if not path:
                self.update_job_objects(path, ds, status="Skipped")
                logging.info("Missing datastream path for '{0}'".format(ds))
                continue
            name = os.path.splitext(os.path.basename(path))[0]
            label = self.set_ds_label(ds, name)

            # 3 ways to move forward with adding datastream:
            # The object is new to the repository,
            # the object is not new, but the datastream should be replaced,
            # or the object is not new and the datastream doesn't yet exist.

            if ((self.new_object and self.ingest_job.process_new == 'y') or (ds not in self.current_ds_list and self.ingest_job.process_existing == 'y'))\
                and ds in self.datastream_paths:

                status, result = self.fedora_api.add_datastream(
                    self.pid, ds, path,
                    controlGroup="M",
                    dsLabel=label,
                    versionable="false",
                    mimeType=self.get_datastream_value(ds, "mimetype"),
                    logMessage="Adding DS: {0} to PID: {1}".format(ds, self.pid)
                )
            elif self.ingest_job.replace_on_duplicate == 'y' and ds in self.datastream_paths:

                status, result = self.fedora_api.add_datastream(
                    self.pid, ds,
                    filepath=path,
                    controlGroup="M",
                    dsLabel=label,
                    versionable="false",
                    mimeType=self.get_datastream_value(ds, "mimetype"),
                    logMessage="Adding DS: {0} to PID: {1}".format(ds, self.pid)
                )
            else:
                status = 200
                logging.info("Not updating or creating datastream: {0} for PID: {1}".format(ds, self.pid))

            if status not in [200, 201]:
                self.update_job_objects(path, ds, status="Failure")
                logging.info("Failed to add or modify datastream: {0} for pid: {1} with error {2}: {3}".format(ds, self.pid, status, result))

            else:
                self.update_job_objects(path, ds)

    def update_job_objects(self, path, ds, status="Success"):
        """Set datastream result. 
        Valid options for status: Success, Failure, Skipped
        """
        result_object = object_results.objects.get(label=status)
        datastream_object = datastreams.objects.get(datastream_label=ds)
        job_objects.objects.create(
                    job_id=self.ingest_job.job_id,
                    created=timezone.now(),
                    obj_file=path,
                    result_id=result_object,
                    pid=self.pid,
                    datastream_id=datastream_object,
            )

    def set_ds_label(self, ds, name):
        """Establish label for datastream.

        args:
            ds(str): name of datastream, e.g. TN, MODS, JPG
            name(str): current name value based on file name.
        """
        if self.collection["use_dynamic_label"] == "True":
            label = name
        else:
            label = self.get_datastream_value(ds, "label")

        return label

    def combine_settings(self, dict1, dict2):
        """Combine *sub*-dictionaries within dictionaries.
        
        Note: argument order matters! The dict1 is the base, whose values will
        be overwritten by dict2 when there is a key collision.

        args:
            dict1(dict): base dictionary to be updated.
            dict2(dict): new dictionary to "add" to dict1.
        """
        new_dict = {}
        for key, value in dict1.items():
            new_value = value.copy()
            if key in dict2:
                new_value.update(dict2[key])
            new_dict[key] = new_value

        return new_dict

    def get_date(self, dc_path):
        """Return DC date from xml."""
        return self.get_dc_element(dc_path, "//dc:date")

    def get_title(self, dc_path):
        """Check DC xml file for title."""
        title = self.get_dc_element(dc_path, "//dc:title")
        # Adjust title to stay under Fedora's 256 character limit.
        if len(title) > 255:
            title = title[:252] + "..."
        return title

    def get_dc_element(self, dc_path, xpath):
        """Use dc_path and xpath to retrieve element content."""

        if dc_path is None:
            return "Test Value"
        xml = etree.parse(dc_path)
        root = xml.getroot()
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        element = root.xpath(xpath, namespaces=ns)
        return element[0].text

    def check_for_existing_object(self):
        """Check if object already exists in repository based on unique ID."""
        # In the event this is an object type that was not selected to have any datastreams ingested/replaced
        # then we want to skip the object. For example, if it is a compound object and the parent object was
        # not selected to have datastreams ingested/replaced
        if "DC" not in self.datastream_paths:
            self.prognosis = "skip"
            logging.info("Object folder missing 'DC' metadata: {0}".format(self.path))
            return

        # Try to get DC identifier with "local:" as prefix. If doesn't exist, get other ID.
        object_id = self.get_preferred_identifier(self.datastream_paths["DC"])

        if not object_id:
            object_id = self.get_identifier(self.datastream_paths["DC"])

        logging.info("Checking for objects with ID: {0}".format(object_id))
        
        self.pids = self.get_pids_in_namespace(object_id, self.namespace)
        
        if self.compound:
            self.pid = self.get_compound_pid()

        if self.child:
            self.pid = self.get_child_pid()

        # If no pid returned in search.
        if len(self.pids) == 0 or not self.pid:

            logging.info("Unable to find appropriate object matching '{0}' in namespace: {1}".format(object_id, self.namespace))
            self.no_pid_returned()
            logging.info("Assigned new pid: {0}".format(self.pid))
            self.prognosis = "ingest"
            self.new_object = True


        elif self.ingest_job.replace_on_duplicate == 'y':
            if len(self.pids) > 1:
                message = "Found more than 1 matching pid for id: {0}. Updating {1}".format(object_id, self.pids[0])
                job_messages.objects.create(job_id=self.ingest_job, message=message, created=timezone.now())                
                logging.warning("Found more than 1 matching pid. Processing {0}".format(self.pids[0]))
            self.pid = self.pids[0]   
            logging.info("----Replacing datastreams")        
            self.prognosis = "ingest"

        else:
            self.duplicate_pid = self.pids[0]
            logging.info("--Existing pid found; Not replacing datastreams; Skipping item.")
            self.prognosis = "skip"

    def get_compound_pid(self):
        """In cases where multiple pids are returned, find compound object Pid."""
        compound_pid = None
        for pid in self.pids:
            status, object_profile = self.fedora_api.get_object_profile(pid=pid)
            if status == 200:
                if self.is_compound(object_profile):
                    compound_pid = pid
                    break
        return compound_pid

    def get_child_pid(self):
        """Method of returning child object's PID by checking for sequence matches."""
        child_pid = None
        sequence_match = 0
        predicate = self.set_sequence_predicate()
        logging.info("predicate: {0}".format(predicate))
        for pid in self.pids:
            # Get content models.
            status, object_profile = self.fedora_api.get_object_profile(pid=pid)

            # Get RELS-EXT data.
            status, rels_ext = self.fedora_api.get_relationships(pid)
            predicates = self.get_predicates(rels_ext)
            if predicate in predicates:
                sequence_match = get_predicate_value(predicate)

            if not self.is_compound(object_profile) and int(sequence_match) == int(self.sequence):
                child_pid = pid
        logging.info("child_pid set at {0}".format(child_pid))
        return child_pid

    def is_compound(self, object_profile):
        """Check to see if a particular content model corresponds to a compound type.

        args:
            object_profile(xml string): object profile returned from repo.
        """
        compound = False
        compound_types = ["info:fedora/islandora:compoundCModel",
                          "info:fedora/islandora:newspaperIssueCModel"]
        cmodels = self.get_content_models(object_profile)
        if any([c in compound_types for c in cmodels]):
            compound = True
        return compound

    def get_predicates(self, rels_ext, format="nt"):
        """Return all predicates in a given rels_ext datastream."""
        g = Graph()
        content = g.parse(data=rels_ext, format=format)
        return list(content.predicates())

    def get_predicate_value(self, rels_ext, predicate, format_="nt"):
        return self.get_predicate_values(rels_ext, predicate, format_=format_)[0]

    def get_predicate_values(self, rels_ext, predicate, format_="nt"):
        values = []
        g = Graph()
        content = g.parse(rels_ext, format=format_)
        for subject, object_ in content.subject_objects(URIRef(predicate)):
            values.append(str(object_))
        return values

    def get_content_models(self, object_profile):
        """Get content models from object profile xml."""
        tree = etree.fromstring(object_profile)
        ns = {"f": "http://www.fedora.info/definitions/1/0/access/"}
        models = tree.xpath("//f:objModels/f:model", namespaces=ns)
        return [m.text for m in models]

    def no_pid_returned(self):
        """If no pid is found for current object, create new one."""
        status, pid_xml = self.fedora_api.get_next_pid(self.namespace)
        self.pid = self.extract_pid(pid_xml)

    def gather_paths(self):
        """Gather paths for all derivatives.

        Use dictionary in which key is the datastream name and value is
        the pattern to match in the filename.
        """
        datastream_paths = {}
        all_datastreams = self.file_datastreams.copy()
        all_datastreams.update(self.metadata_datastreams)

        # Attempt to match file in the directory that matches a given datastream.
        for f in os.listdir(self.path):
            for ds_name, ds_pattern in all_datastreams.items():
                # Check if any of the included patterns match the file.
                if any([ds.lower() in f.lower() for ds in ds_pattern]) and not f.startswith("."):
                    datastream_paths[ds_name] = os.path.join(self.path, f)
        return datastream_paths

    def get_preferred_identifier(self, dc_path):
        """Attempt to get valid identifier.

        Check first for PID in the Dublin Core. Failing that look for "local:" ID.

        args:
            dc_path(str): path to dublin core file.
        """
        idmatch = None
        idlist = self.get_identifiers(dc_path)
        for i in idlist:
            if self.is_pid(i):
                idmatch = i
                break
        if not idmatch:
            idmatch = self.get_identifier_with_prefix(idlist, "local:")

        return idmatch

    def is_pid(self, identifier):
        """Check to see if given ID is 'pid-like.'

        args:
            identifier(str): id from DC file.
        """
        pid1 = False
        pid2 = False
        id_parts = identifier.split(":")
        if len(id_parts) == 2:
            if id_parts[0] != "local" and all((c.isdigit() or c.isalpha()) for c in id_parts[0]):
                pid1 = True
            if id_parts[1].isdigit():
                pid2 = True

        return pid1 and pid2

    def get_identifier_with_prefix(self, idlist, prefix):
        """Get identifiers and limit by a prefix at its start.

        args:
            idlist(list): list of identifiers from DC file.
            prefix(str): prefix to check against for match.
        """
        idmatch = None
        for i in idlist:
            if i.startswith(prefix):
                idmatch = i
                break
        return idmatch

    def get_identifier(self, dc_path):
        """Return first result from identifier search.

        In many cases, only 1 id will be returned; this represents
        a simple way of accessing that 1 id.

        args:
            dc_path(str): full path and file name of DC record.

        returns:
            (str): string of first id in list.
        """
        idlist = self.get_identifiers(dc_path)
        return idlist[0]

    def get_identifiers(self, dc_path):
        """Search for identifier from DC and return all matches.

        args:
            dc_path(str): path to DC file.
        returns:
            idlist(list): all ids that match the given query.
        """
        id_xpath = "//dc:identifier"
        xml = etree.parse(dc_path)
        root = xml.getroot()
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        ids = root.xpath(id_xpath, namespaces=ns)
        idlist = [i.text for i in ids if i.text is not None]
        return idlist

    def get_pids_in_namespace(self, fileid, pidspace):
        """Use base filename to check for existing object in repo.

        args:
            filename(str): filename of object, which should be included in dc:identifier.
            pidspace(str): pid namespace for which to return a pid.
        """
        pids = None
        status, xml = self.fedora_api.find_objects_by_id(fileid)
        if status == 200:
            tree = etree.fromstring(xml)
            ns = {"f": "http://www.fedora.info/definitions/1/0/types/"}
            objs = tree.xpath("//f:pid", namespaces=ns)
            pids = [o.text for o in objs if o.text.split(":")[0] == pidspace]
        for pid in pids:
            logging.info("----Found matching PID: {0}".format(pid))
        return pids

    def set_datastreams(self):
        """Set metadata and file datastreams according to collection configs and object layer."""

        # Datastreams are labeled according to object type. Extract just those from current object type.
        self.object_datastreams = [ds[0] for ds in self.datastreams if ds[1] == self.object_type]
        logging.info("object_datasterams {0}".format(self.object_datastreams))
        return self.sort_datastreams()

    def sort_datastreams(self):
        """"Sort datastreams as either relating to files or to metadata."""
        files = {}
        metadata = {}
        for ds in self.object_datastreams:
            # Check in collection profile to see if the datastream corresponds to a file object or metadata.
            if ds in self.objects[self.object_type]["datastreams"]:
                files[ds] = self.get_datastream_value(ds, "marker")
            elif ds in self.objects[self.object_type]["metadata"]:
                metadata[ds] = self.get_datastream_value(ds, "marker")
            else:
                logging.warning("Datastream label '{0}' not found in collection profile. Skipping.".format(ds))
        return files, metadata

    def get_next_pid(self, namespace):
        """Get next pid in namespace."""
        response = self.api.getNextPID(namespace=namespace)
        return self.extract_pid(response.content)

    def extract_pid(self, xml):
        """Extract pid from xml string.

        args:
            xml(str): xml content in string.
        """
        tree = etree.fromstring(xml)
        return tree.getchildren()[0].text

    def object_exists(self):
        """Check if object exists to confirm success of ingest.

        args:
            pid(str): pid in format namespace:number
        """
        pid_check = list(self.repo.find_objects(pid=self.pid))
        if len(pid_check) == 1:
            return True
        else:
            logging.info("Failed to ingest {0}".format(self.pid))
            return False

    def generate_checksum(self, file_path):
        """Return SHA-512 checksum for given file.

        Could cause errors if file is extremely large.
        args:
            file_path(str)
        returns:
            (str) containing only hexadecimal digits.
        """
        sha = hashlib.sha512()
        with open(file_path, "rb") as f:
            while True:
                data = f.read(2**10)
                if not data:
                    break
                sha.update(data)
        return sha.hexdigest()

    def get_root_dir(self):
        """Find root directory, which should end in _root.

        args:
            path(str): path to files to tally
        """
        path = self.ingest_job.source_dir 
        root_dir = path
        for root, dirs, files in os.walk(path):
            for dirx in dirs:
                if dirx.endswith("_root"):
                    root_dir = os.path.join(root, dirx)
                    break

        return root_dir
