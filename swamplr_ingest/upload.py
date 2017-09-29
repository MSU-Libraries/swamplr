"""Fedora Commons Object classes and upload code."""
from rdflib import URIRef, XSD
from rdflib.namespace import Namespace
from eulfedora.models import FileDatastream, Relation, DigitalObject, DatastreamObject
from eulxml import xmlmap
import hashlib
import logging
from datetime import datetime

fedora_ns = Namespace(URIRef("info:fedora/fedora-system:def/relations-external#"))
islandora_ns = Namespace(URIRef("http://islandora.ca/ontology/relsext#"))
premis_ns = Namespace(URIRef("http://www.loc.gov/premis/rdf/v1#"))
prov_ns = Namespace(URIRef("http://www.w3.org/ns/prov#"))
fedora_model = Namespace(URIRef("info:fedora/fedora-system:def/model#"))


class LocalObject(DigitalObject):
    """Object class for features common to all repository objects."""
    batch_id = Relation(prov_ns.wasGeneratedBy, ns_prefix={"prov": prov_ns}, rdf_type=XSD.int)
    batch_timestamp = Relation(prov_ns.wasGeneratedAtTime, ns_prefix={"prov": prov_ns}, rdf_type=XSD.dateTime)
    has_model = Relation(fedora_model.hasModel, ns_prefix={"fedora-model": fedora_model}, rdf_type=XSD.anyURI)
    is_member_of_collection = Relation(fedora_ns.isMemberOfCollection, ns_prefix={"fedora-rels-ext": fedora_ns})
    constituent = Relation(fedora_ns.isConstituentOf, ns_prefix={"fedora": fedora_ns})
    is_member_of = Relation(fedora_ns.isMemberOf, ns_prefix={"fedora-rels-ext": fedora_ns})
    is_sequence_number = Relation(islandora_ns.isSequenceNumber, ns_prefix={"islandora": islandora_ns})
    is_sequence_of = Relation(islandora_ns.isSequenceOf, ns_prefix={"islandora": islandora_ns})


class Upload:
    """Class for creating digital objects in fedora commons using the EulFedora library."""

    def __init__(self, pid, repo, api, job_id, ingest_meta_class, new_object=True,
                 object_label=u"Fedora Commons Object"):
        """
        Initialize controls for new object.

        Positional arguments:
        pid(str) -- unique id for object, e.g. collection:34.
        repo (repo) -- repository connection object generated via EulFedora.
        job_id(int) -- job ID for current batch running in repo-ingest.
        object_type(class) -- a custom class object.
        kwargs:
            object_label (str) -- label for object
            new_object(bool): true if new object should be created
        """
        self.repo = repo
        self.api = api
        self.job_id = str(job_id)
        self.pid = pid
        self.ingest_meta_class = ingest_meta_class
        self.ingest_class = ingest_meta_class(api)
        self.new_object = new_object
        self.object_label = object_label
        self.obj = None
        self.build_object()

    def build_object(self):
        """Create object using specified pid and object type."""
        IngestObject = self.ingest_meta_class
        self.obj = self.repo.get_object(pid=self.pid, type=IngestObject, create=self.new_object)
        self.obj.label = self.object_label
        self.obj.rels_ext.label = "RDF External Relationships"
        self.obj.save()
        self._update_rels_ext() 

    def add_file_datastream(self, file_path, ds_id, label, mimetype, checksum_type, versionable):
        """Add file to repository.

        Will not work unless file:// location is on the fedora server."""

        logging.info("----adding datastream {0}: {1}".format(ds_id, label))
       
        """ 
        if ds_id in self.obj.ds_list:
            self.api.purgeDatastream(self.pid, ds_id)
        """
        """
        with open(file_path) as open_file:
            setattr(eval("self.obj." + ds_id.lower()), "checksum_type", checksum_type)
            setattr(eval("self.obj." + ds_id.lower()), "checksum", self.generate_checksum(file_path))
            setattr(eval("self.obj." + ds_id.lower()), "content", open_file)
            setattr(eval("self.obj." + ds_id.lower()), "label", label)
            setattr(eval("self.obj." + ds_id.lower()), "versionable", eval(versionable))
            setattr(eval("self.obj." + ds_id.lower()), "mimetype", mimetype)
            self.obj.save()
        """
        if checksum_type == "SHA-512":
            checksum = self.generate_checksum(file_path)

        else:
            checksum = None
            logging.warning("Unable to generate checksum for specified type: {0}".format(checksum_type))
        new_datastream = DatastreamObject(self.obj, ds_id, label,
                                          mimetype=mimetype,
                                          control_group="M",
                                          checksum_type=checksum_type,
                                          checksum=checksum,
                                          versionable=versionable)
        with open(file_path, "rb") as f:
            new_datastream.content = f.read()
        new_datastream.label = label
        new_datastream.mimetype = mimetype
        new_datastream.save()
    
    def add_xml_datastream(self, xml_path, ds_id, label, control_group, mimetype, checksum_type):
        """Add XML object."""
        xml_object = xmlmap.load_xmlobject_from_file(xml_path)

        if checksum_type == "SHA-512":
            checksum = self.generate_checksum(xml_path)

        else:
            checksum = None
            logging.warning("Unable to generate checksum for specified type: {0}".format(checksum_type))

        logging.info("----adding datastream {0}: {1}".format(ds_id, label))

        new_datastream = DatastreamObject(self.obj, ds_id, label,
                                          mimetype=mimetype,
                                          control_group=control_group,
                                          checksum_type=checksum_type,
                                          checksum=checksum)

        new_datastream.content = xml_object
        new_datastream.label = label
        new_datastream.save()

    def build_rels_ext(self, s_predicate, s_object, delete_existing=False):
        """Add relationship to specified object's RELS-EXT datastream.

        args:
            s_predicate (str): the URI of a predicate
            s_object (str): URI or literal of an object (objects beginning with "info:fedora/" will be treated as resource,
                otherwise as a literal)
        kwargs:
            delete_existing(bool): if true, delete any statements using s_predicate.
        """
        if delete_existing:
            self._delete_relationship_by_predicate(s_predicate)
        self.obj.add_relationship(s_predicate, s_object)
        self.obj.save()

    def update_title(self, title, page):
        """Update title for paged content."""
        self.obj.label = "{0} Page {1}".format(title, page)
        self.obj.save()

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

    def set_attr(self, attr, value, sub_attr=""):
        """Add specified attribute and value to object."""
        if sub_attr != "":
            setattr(eval("self.obj." + attr), sub_attr, value)
        else:
            setattr(self.obj, attr, value)
        logging.info("----processing {0} {1}".format(attr, sub_attr))
        self.obj.save()

    def set_attr_xml_content(self, attr, path):
        """Add xml content to datastream."""
        xml_object = xmlmap.load_xmlobject_from_file(path)
        xml_object = open(path)
        if attr == "dc":
            self.set_attr(attr+".content", xml_object, sub_attr="dc")
        else:
            self.set_attr(attr, xml_object, sub_attr="content")

    def set_dc_ident_attr(self, ident):
        """Add new DC identifier."""
        self.obj.dc.identifier = ident
        self.obj.save()

    def set_attr_label(self, attr, label):
        """Add label to datastream."""
        self.set_attr(attr, label, sub_attr="label")

    def set_attr_file_content(self, attr, path):
        """Add file content to datastream."""
        self.set_attr(attr, open(path), sub_attr="content")

    def set_attr_file_checksum(self, attr, path):
        """Add checksum.

        N.B. - Only 1 checksum type currently supported.
        """
        checksum = self.generate_checksum(path)
        self.set_attr(attr, checksum, sub_attr="checksum")

    def _update_rels_ext(self):
        """Delete and replace RELS-EXT with clean version."""
        self._set_batch_provenance()
        self._add_provenance()
        self.obj.save()

    def _set_batch_provenance(self):
        """Establish id and timestamp for old vs. new objects."""
        if not self.new_object:
            self.batch_id = getattr(self.obj, "batch_id", self.job_id)
            if self.batch_id is None:
                self.batch_id = self.job_id
            self.batch_timestamp = getattr(self.obj, "batch_timestamp", self._get_time())
            if self.batch_timestamp is None:
                self.batch_timestamp = self._get_time()
        else:
            self.batch_id = self.job_id
            self.batch_timestamp = self._get_time()

    def _get_time(self):
        """Return datetime string with microseconds truncated."""
        dt = datetime.now().replace(microsecond=0)
        return dt.isoformat()

    def _add_provenance(self):
        """Add batch info to RELS-EXT."""
        self.set_attr("batch_id", int(self.batch_id))
        self.set_attr("batch_timestamp", self.batch_timestamp)
        """
        self.obj.batch_id = int(self.batch_id)
        self.obj.batch_timestamp = self.batch_timestamp
        """

    def delete_rels_ext_statement(self, s_predicate, s_object):
        """Delete particular RELS-EXT relationship specified by predicate and object.

        args:
            s_predicate (str): the URI of a predicate
            s_object (str): URI or literal of an object (objects beginning with "info:fedora/" will be treated as resource,
                otherwise as a literal)
        """
        self.obj.purge_relationship(s_predicate, s_object)
        self.obj.save()

    def _delete_relationship_by_predicate(self, predicate):
        """Delete all relationships in RELS-EXT using a given predicate.

        args:
            predicate(str): the URI of an RDF predicate.
        """
        # TODO: find way to delete all relationships containing a given predicate; obstacle
        # is that the Fedora API call that deletes relationships requires both predicate and object;
        # it would be preferable to delete any arbitrary relationship that contains a given predicate.
        pass
