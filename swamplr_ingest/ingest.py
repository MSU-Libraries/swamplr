"""Ingest code for Large Image objects."""
import logging
from lxml import etree
from upload import Upload, LocalObject
from rdflib import URIRef, XSD
from rdflib.namespace import Namespace
from eulfedora.models import XmlDatastream, FileDatastream, Relation, DigitalObject, DatastreamObject
from eul_proj import settings
from job_queue import JobQueue
from msulrepo import repo
from hint import HintFiles
from operator import itemgetter
import os
import re
import json

fedora_ns = Namespace(URIRef("info:fedora/fedora-system:def/relations-external#"))
islandora_ns = Namespace(URIRef("http://islandora.ca/ontology/relsext#"))
premis_ns = Namespace(URIRef("http://www.loc.gov/premis/rdf/v1#"))
prov_ns = Namespace(URIRef("http://www.w3.org/ns/prov#"))
fedora_model = Namespace(URIRef("info:fedora/fedora-system:def/model#"))


class Ingest:

    """Process ingest of collection to Fedora Commons."""

    def __init__(self, path, ingest_job, collection_configs, datastreams, object_type,
                 job_id, compound=False, child=False, parent_pid=None, sequence=None):
        """Prepare for ingest."""

        # Path to object directory (containing datastream files).
        self.path = path

        # Assessed type of object, e.g. compound, large_image, pdf, etc.
        self.object_type = object_type

        # All job details from database.
        self._ingest_job = ingest_job
        self._job_id = job_id
        self._namespace = self._ingest_job.namespace

        # All collection configs for the given collection name.
        self._collection_configs = collection_configs
        self._objects = self._collection_configs["objects"]
        self._content_model = self._collection_configs["objects"][object_type]["content_model"]
        
        # Configs compiled from collection_defaults.json and collections.json.
        self.metadata_configs = {}
        self.datastream_configs = {}

        # Load default settings.
        self._load_datastream_settings()

        self._compound = compound
        self._child = child
        self._parent_pid = parent_pid
        self._sequence = sequence

        # List of datastreams as 2-tuple (name, associated object type).
        self._datastreams = datastreams

        # Future Upload class.
        self._object_upload = ""

        # Future title.
        self.title = ""

        # Connect to Fedora repository.
        repo_server = settings.CURRENT_INGEST_SERVER
        self._repo = repo.repo_connect(repo_server)
        self._api = repo.api_connect(repo_server)

        # Outlook and outcome.
        self.prognosis = "skip"
        self.result = "failed"

        # True if a new object is being created, false if one already exists.
        self._new_object = False

        # Just datastreams at the current layer, e.g. compound parent objects.
        self._object_datastreams = []

        # Extract and separate file datastreams from metadata according to current object layer.
        self.file_datastreams, self.metadata_datastreams = self._set_datastreams()

        # Dictionary containing datastream id as key, path to file as value.
        self.datastream_paths = self._gather_paths()
       
        # Treat given object as new.
        if self._ingest_job.ingest_only_new_objects:
        
            # Create object as new, not using existing pid.
            self._new_object = True

            # Create new pid.
            self.pid = self._get_next_pid(self._namespace)

            # Ingest shall proceed.
            self.prognosis = "ingest"
        
        # Otherwise check for given object in the repository.
        else:
            self._check_for_existing_object()

    def create_object(self):
        """Create object for upload, whether a new object or amended."""

        # Create object class that extends DigitalObject.
        object_class = self._create_object_class()

        # Title is pulled from Dublin Core, and used as FC label.
        self.title = self._get_title(self.datastream_paths.get("DC", None))

        # This method attempts to find root directory in a sub- or parent directory.
        self._root_dir = self._get_root_dir()

        # Get data from hint files.
        hint = HintFiles(self._root_dir, self.path)
        self._hint_data = hint.get_hint_data()
        
        logging.info(u"Processing object at {0}: {1}".format(self.pid, self.title))

        # Pass data over to upload class to begin upload to Fedora.
        self._object_upload = Upload(
            self.pid, self._repo, self._api, self._job_id, object_class,
            new_object=self._new_object,
            object_label=self.title
        )

        # Add rels-ext, metadata, files, then check outcome.
        self._add_rels_ext()
        self._add_metadata()
        self._add_files()
        self._check_object()

    def _add_rels_ext(self):
        """Add basic rels-ext for object."""

        # Load default settings for content model.
        cmodels = self._load_content_model_settings()
        has_model_object = cmodels[self._content_model]["has_model"]

        # Root pid, e.g. "etd:root" made by joining namespace and "root".
        root_pid = ":".join([self.pid.split(":")[0], "root"])

        logging.info("Adding relations at {0}".format(self.pid))

        # self._object_upload.set_attr("is_member_of_collection", 'info:fedora/{0}'.format(root_pid))
        # self._object_upload.set_attr("has_model", has_model_object)

        self._object_upload.build_rels_ext("info:fedora/fedora-system:def/model#hasModel", has_model_object)

        if self._content_model == "newspaper_issue":
            self._object_upload.build_rels_ext("info:fedora/fedora-system:def/relations-external#isMemberOf",
                                               "info:fedora/{0}".format(root_pid.replace("root", "1")))
            self._object_upload.build_rels_ext("http://islandora.ca/ontology/relsext#isSequenceNumber", self._sequence)
            self._object_upload.build_rels_ext("http://islandora.ca/ontology/relsext#dateIssued",
                                               self._get_date(self.datastream_paths.get("DC", None)))

        elif self._child:

            if self._content_model == "newspaper_page":
                self._object_upload.build_rels_ext("http://islandora.ca/ontology/relsext#isSequenceNumber", self._sequence)
                self._object_upload.build_rels_ext("http://islandora.ca/ontology/relsext#isPageNumber", self._sequence)

                self._object_upload.build_rels_ext("http://islandora.ca/ontology/relsext#isPageOf",
                                                   "info:fedora/{0}".format(self._parent_pid))

                self._object_upload.build_rels_ext("info:fedora/fedora-system:def/relations-external#isMemberOf",
                                                   "info:fedora/{0}".format(self._parent_pid))
                self._object_upload.update_title(self.title, self._sequence)

            else:
                # Child object is 'constituent of' parent.
                self._object_upload.build_rels_ext("info:fedora/fedora-system:def/relations-external#isConstituentOf",
                                                   "info:fedora/{0}".format(self._parent_pid))

                sequence_predicate = self._set_sequence_predicate()
                self._object_upload.build_rels_ext(sequence_predicate, self._sequence)

        else:

            # Using build_rels_ext method instead of set_attr method because the latter does not seem to be able to handle
            # URIs as objects, only literals.
            self._object_upload.build_rels_ext("info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
                                               "info:fedora/{0}".format(root_pid))

        if self._hint_data.get("sequence", "false") == "true":
 
            # Set values for sequence name and sequence value.
            self._process_dir_sequence()
            """
            self._object_upload._add_attr("is_sequence_of", sequence_name)
            self._object_upload._add_attr("is_sequence_number", sequence_number)
            """
            self._object_upload.build_rels_ext("http://islandora.ca/ontology/relsext#isSequenceNumber", self.sequence_value)
            self._object_upload.build_rels_ext("http://islandora.ca/ontology/relsext#isSequenceOf", self.sequence_term)
            

    def _process_dir_sequence(self):
        """Use sequence settings in hint file to assign appropriate sequence RELS-EXT."""
        
        # Regex pattern to match and use for sorting.
        pattern = self._hint_data["sequence_match"]
      
        # Remove trailing slash.
        object_path = self._normalize_path()
        # logging.info("object path: {0}".format(object_path))

        # The sort directory is the root directory plus a number of steps down.
        path_length = len(self._root_dir.split("/")) + self._hint_data["sort_level"]
        # logging.info("path lengthi: {0}".format(path_length))

        # Divide and re-combine path of appropriate depth.
        sort_path_parts = object_path.split("/")[:path_length]

        # sort_path is the directory *containing* the elements that should be sorted.
        sort_path = "/" + os.path.join(*sort_path_parts)
        # logging.info("sort path: {0}".format(sort_path))

        # object_leaf is the sortable element for the given object and settings.
        object_leaf = object_path.split("/")[path_length]
        # logging.info("object leaf: {0}".format(object_leaf))

        filter_key = self._hint_data["filter_by"]
        sort_key = self._hint_data["sort_by"]

        filter_term, sort_value = self._get_matches(pattern, object_leaf, filter_key, sort_key)

        filtered = []

        for sub in [f for f in sorted(os.listdir(sort_path)) if os.path.isdir(os.path.join(sort_path, f))]:

            current_object = False
            # logging.info("sub dir: {0}".format(sub))
            subterm, subkey = self._get_matches(pattern, sub, filter_key, sort_key)

            if sub == object_leaf:
                current_object = True

            if subterm == filter_term:
                filtered.append((subterm, float(subkey), current_object))
        
        self._set_sequence_values(filtered)

    def _set_sequence_values(self, slist):

        sort_order = self._hint_data["sort_direction"]
        slist.sort(key=itemgetter(1), reverse=(sort_order=="desc"))
        for index, values in enumerate(slist):
            if values[2]:
                self.sequence_value = index + 1
                self.sequence_term = values[0]

    def _get_matches(self, pattern, text, *keys):
        """Get named matches from string."""
        values = []
        match = re.match(pattern, text)
        for key in keys:
            if key in match.groupdict():
                values.append(match.group(key))
            else:
                values.append(None)

        return values

    def _normalize_path(self):
        """Remove trailing slash."""
        path = self.path
        if self.path.endswith("/"):
            path = path[:-1]
        return path

    def _get_root_dir(self):
        """Get dirpath that ends in '*:root'."""
        root_dir = JobQueue.get_root_dir(self.path)
        path_sub_dirs = root_dir.rsplit("/")[1:]
        dirs = []
        for p in path_sub_dirs:
            dirs.append(p)
            if "_root" in p:
                break
        return "/" + os.path.join(*dirs)

    def _set_sequence_predicate(self):
        """Set up predicate to record/check sequence number of child object."""
        if self._content_model == "newspaper_page":
            predicate = "http://islandora.ca/ontology/relsext#isSequenceNumber"
        else:
            # Sequence predicate for compound object children.
            pid_underscore = self._parent_pid.replace(":", "_")
            predicate = "http://islandora.ca/ontology/relsext#isSequenceNumberOf{0}".format(pid_underscore)
        return predicate

    def _add_metadata(self):
        """Add metadata datastreams."""
        logging.info("Adding metadata at {0}".format(self.pid))
        for ds in self.metadata_datastreams:
            # 3 ways to move forward with adding datastream:
            # The object is new to the repository, the object is not new, but the datastream should be replaced,
            # or the object is not new and the datastream doesn't yet exist.

            if (self._new_object or
               self._ingest_job.replace or
               ds not in self._object_upload.obj.ds_list) and ds in self.datastream_paths:

                # ds_lower = ds.lower()
                path = self.datastream_paths[ds]
                name = os.path.splitext(os.path.basename(path))[0]
                label = self._set_ds_label(ds, name)

                self._object_upload.add_xml_datastream(
                    path, ds, label,
                    self.metadata_configs[ds]["type"],
                    self.metadata_configs[ds]["mimetype"],
                    self.metadata_configs[ds]["checksum_type"])

        if self._child:
            # For child objects, establish additional unique ID that combines generic ID and sequence number.
            object_id = self._get_identifier(self.datastream_paths["DC"])
            child_object_id = "{0}-{1}".format(object_id, "{:03d}".format(int(self._sequence)))

            self._object_upload.set_dc_ident_attr(child_object_id)

    def _add_files(self):
        """Create file datastreams for large image objects."""
        logging.info("Adding objects at {0}".format(self.pid))

        for ds in self.file_datastreams:

            # 3 ways to move forward with adding datastream:
            # The object is new to the repository, the object is not new, but the datastream should be replaced,
            # or the object is not new and the datastream doesn't yet exist.

            if (self._new_object or
               self._ingest_job.replace or
               ds not in self._object_upload.ds_list) and ds in self.datastream_paths:
                # ds_lower = ds.lower()
                path = self.datastream_paths[ds]
                name = os.path.splitext(os.path.basename(path))[0]

                label = self._set_ds_label(ds, name)
                self._object_upload.add_file_datastream(path, ds, label,
                                                        self.datastream_configs[ds]["mimetype"],
                                                        self.datastream_configs[ds]["checksum_type"],
                                                        self.datastream_configs[ds]["versionable"])

    def _set_ds_label(self, ds, name):
        """Establish label for datastream.

        args:
            ds(str): name of datastream, e.g. TN, MODS, JPG
            name(str): current name value based on file name.
        """
        if self._collection_configs["use_dynamic_label"] == "True":
            label = name
        else:
            label = self.metadata_configs[ds]["label"]

        return label

    def _create_object_class(self):
        """Create object class to extend DigitalObject."""
        """
        attributes = {
            "batch_id": Relation(prov_ns.wasGeneratedBy, ns_prefix={"prov": prov_ns}, rdf_type=XSD.int),
            "batch_timestamp":  Relation(prov_ns.wasGeneratedAtTime, ns_prefix={"prov": prov_ns}, rdf_type=XSD.dateTime),
            "has_model": Relation(fedora_model.hasModel, ns_prefix={"fedora-model": fedora_model}, rdf_type=XSD.anyURI),
            "is_member_of_collection": Relation(fedora_ns.isMemberOfCollection, ns_prefix={"fedora-rels-ext": fedora_ns}),
            "constituent": Relation(fedora_ns.isConstituentOf, ns_prefix={"fedora": fedora_ns}),
            }
        """
        attributes = {}
        for ds_name, ds_values in self.metadata_configs.items():
            if ds_name in self.metadata_datastreams and ds_name != "DC":
                defaults = {
                    "versionable": eval(ds_values["versionable"]),
                    "checksum_type": ds_values["checksum_type"],
                    "mimetype": ds_values["mimetype"]
                }
                attributes[ds_name.lower()] = FileDatastream(ds_values["id"], ds_values["label"], defaults=defaults)

        for ds_name, ds_values in self.datastream_configs.items():
            if ds_name in self.file_datastreams:
                defaults = {
                    "versionable": ds_values["versionable"],
                    "checksum_type": ds_values["checksum_type"],
                    "mimetype": ds_values["mimetype"]
                }
                attributes[ds_name.lower()] = FileDatastream(ds_values["id"], ds_values["label"], defaults=defaults)

        if self._child:
            pid_underscore = self._parent_pid.replace(":", "_")
            sequence_predicate = "islandora_ns.isSequenceNumberOf{0}".format(pid_underscore)
            attributes["sequence"] = Relation(eval(sequence_predicate), ns_prefix={"islandora": islandora_ns})

        # Construct metaclass.
        ingest_meta_class = type("IngestObject", (LocalObject,), attributes)
        ingest_meta_class.__module__ = "eulcom.upload"
        ingest_meta_class.__doc__ = "Dynamic class that extends DigitalObject via LocalObject"
        
        return ingest_meta_class

    def _load_datastream_settings(self):
        """Load default- and collection-level settings for datastreams and metadata."""
        
        default_configs = self._load_json(settings.COLLECTION_DEFAULTS)
        
        # Load default metadata configs, then amend with collection-level settings.
        metadata_configs = default_configs["metadata"]
        collection_metadata_configs = self._collection_configs["objects"][self.object_type]["metadata"]
        self.metadata_configs = self._combine_settings(metadata_configs, collection_metadata_configs)

        # Load default datastream configs, then amend with collection-level settings.
        datastream_configs = default_configs["datastreams"]
        collection_datastream_configs = self._collection_configs["objects"][self.object_type]["datastreams"]
        self.datastream_configs = self._combine_settings(datastream_configs, collection_datastream_configs)

    def _combine_settings(self, dict1, dict2):
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

    def _load_content_model_settings(self):
        """Load content model default settings."""
        default_configs = self._load_json(settings.COLLECTION_DEFAULTS)
        return default_configs["content_models"]

    def _load_json(self, path):
        with open(path) as f:
            data = json.load(f)

        return data

    def _get_date(self, dc_path):
        """Return DC date from xml."""
        return self._get_dc_element(dc_path, "//dc:date")

    def _get_title(self, dc_path):
        """Check DC xml file for title."""
        title = self._get_dc_element(dc_path, "//dc:title")
        # Adjust title to stay under Fedora's 256 character limit.
        if len(title) > 255:
            title = title[:252] + "..."
        return title

    def _get_dc_element(self, dc_path, xpath):
        """Use dc_path and xpath to retrieve element content."""

        if dc_path is None:
            return "Test Value"
        xml = etree.parse(dc_path)
        root = xml.getroot()
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        element = root.xpath(xpath, namespaces=ns)
        return element[0].text

    def _check_for_existing_object(self):
        """Check if object already exists in repository based on unique ID."""
        # In the event this is an object type that was not selected to have any datastreams ingested/replaced
        # then we want to skip the object. For example, if it is a compound object and the parent object was
        # not selected to have datastreams ingested/replaced
        if "DC" not in self.datastream_paths:
            self.prognosis = "skip"
            return

        # Try to get DC identifier with "local:" as prefix. If doesn't exist, get other ID.
        object_id = self._get_preferred_identifier(self.datastream_paths["DC"])
        if not object_id:
            object_id = self._get_identifier(self.datastream_paths["DC"])
            logging.info("Checking object ID: {0}".format(object_id))

        self.pid = self._get_pid_by_filename(object_id, self._namespace, return_all_objects=(self._compound or self._child))
        
        if self._compound:
            self.pid = self._get_compound_pid()

        if self._child:
            self.pid = self._get_child_pid()

        # If no pid returned in search.
        if self.pid is None:

            self._no_pid_returned()
            logging.info("Unable to find an object matching {0} in {1}".format(object_id, self._namespace))

        elif self._ingest_job.replace:
        
            self.prognosis = "ingest"

        else:

            self.prognosis = "skip"

    def _get_child_pid(self):
        """Method of returning child object's PID by checking for sequence matches."""
        child_pid = None
        sequence_match = None
        predicate = self._set_sequence_predicate()
        pids = [p for p in self.pid if p.split(":")[0] == self._namespace]
        for pid in pids:
            do = self._repo.get_object(pid=pid)
            for s, p, o in do.rels_ext.content:
                if str(p) == predicate:
                    sequence_match = o
                    break
            if not self._is_compound(do) and int(sequence_match) == int(self._sequence):
                child_pid = pid

        return child_pid

    def _is_compound(self, digital_object):
        """Check to see if a particular content model corresponds to a compound type.

        args:
            digital_object(DigitalObject): object returned from repo.
        """
        compound = False
        compound_types = ["info:fedora/islandora:compoundCModel",
                          "info:fedora/islandora:newspaperIssueCModel"]
        for ct in compound_types:
            if digital_object.has_model(ct):
                compound = True
                break
        return compound

    def _get_compound_pid(self):
        """In cases where multiple pids are returned, find compound object Pid."""
        compound_pid = None
        for pid in self.pid:
            do = self._repo.get_object(pid=pid)
            if self._is_compound(do) and pid.split(":")[0] == self._namespace:
                compound_pid = pid
                break
        return compound_pid

    def _no_pid_returned(self):
        """If no pid is found for current object."""
        self.prognosis = "ingest"
        self._new_object = True
        self.pid = self._get_next_pid(self._namespace)

    def _gather_paths(self):
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

    def _get_preferred_identifier(self, dc_path):
        """Attempt to get valid identifier.

        Check first for PID in the Dublin Core. Failing that look for "local:" ID.

        args:
            dc_path(str): path to dublin core file.
        """
        idmatch = None
        idlist = self._get_identifiers(dc_path)
        for i in idlist:
            if self._is_pid(i):
                idmatch = i
                break
        if not idmatch:
            idmatch = self._get_identifier_with_prefix(idlist, "local:")

        return idmatch

    def _is_pid(self, identifier):
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

    def _get_identifier_with_prefix(self, idlist, prefix):
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

    def _get_identifier(self, dc_path):
        """Return first result from identifier search.

        In many cases, only 1 id will be returned; this represents
        a simple way of accessing that 1 id.

        args:
            dc_path(str): full path and file name of DC record.

        returns:
            (str): string of first id in list.
        """
        idlist = self._get_identifiers(dc_path)
        return idlist[0]

    def _get_identifiers(self, dc_path):
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
        idlist = [i.text for i in ids]
        return idlist

    def _get_pid_by_filename(self, fileid, pidspace, return_all_objects=False):
        """Use base filename to check for existing object in repo.

        args:
            filename(str): filename of object, which should be included in dc:identifier.
            pidspace(str): pid namespace for which to return a pid.
        kwargs:
            return_all_objects(bool): return all matching pids or just one in defined pidspace.
        """
        return repo.get_pid_by_filename(self._repo, fileid, pidspace, return_all_objects=return_all_objects)

    def _set_datastreams(self):
        """Set metadata and file datastreams according to collection configs and object layer."""

        # Datastreams are labeled according to object type. Extract just those from current object type.

        self._object_datastreams = [ds[0] for ds in self._datastreams if ds[1] == self.object_type]
        return self._sort_datastreams()

    def _sort_datastreams(self):
        """"Sort datastreams as either relating to files or to metadata."""
        files = {}
        metadata = {}
 
        for ds in self._object_datastreams:
            # Check in collection profile to see if the datastream corresponds to a file object or metadata.
            if ds in self._objects[self.object_type]["datastreams"]:
                files[ds] = self.datastream_configs[ds]['marker']
            elif ds in self._objects[self.object_type]["metadata"]:
                metadata[ds] = self.metadata_configs[ds]['marker']
            else:
                logging.warning("Datastream label '{0}' not found in collection profile. Skipping.".format(ds))
        return files, metadata

    def _get_next_pid(self, namespace):
        """Get next pid in namespace."""
        response = self._api.getNextPID(namespace=namespace)
        return self._extract_pid(response.content)

    def _extract_pid(self, xml):
        """Extract pid from xml string.

        args:
            xml(str): xml content in string.
        """
        tree = etree.fromstring(xml)
        return tree.getchildren()[0].text

    def _check_object(self):
        """Check result and update database.

        args:
            pid(str): typical pid
            obj_name(str): the path name of the object
        """

        if self._object_exists():
            self.result = "success"
            JobQueue.insert_job_objects(self._job_id, self.path, "success")
            JobQueue.insert_object_pids(self._job_id, self.pid)
        else:
            self.result = "failed"
            JobQueue.insert_job_objects(self._job_id, self.path, "failure")

    def _object_exists(self):
        """Check if object exists to confirm success of ingest.

        args:
            pid(str): pid in format namespace:number
        """
        pid_check = list(self._repo.find_objects(pid=self.pid))
        if len(pid_check) == 1:
            return True
        else:
            logging.info("Failed to ingest {0}".format(self.pid))
            return False
