import requests
from lxml import etree
import os

class FedoraApi():

    """Class for interacting with the fedora API."""

    def __init__(self, base_url="http://localhost:8080/fedora", username=None, password=None):
        """Initialize API by testing connection."""
        self.base_url = base_url
        self.url = base_url
        self.method = "GET"
        self.auth = None
        self.file = None
        if username and password:
            self.auth = (username, password)
        self.static_params = {"resultFormat": "xml"}
        self.dynamic_params = {}

        self.valid_datatype_uris = [
            "http://www.w3.org/2001/XMLSchema#int",
            "http://www.w3.org/2001/XMLSchema#double",
            "http://www.w3.org/2001/XMLSchema#float",
            "http://www.w3.org/2001/XMLSchema#dateTime",
            "http://www.w3.org/2001/XMLSchema#long",
        ]

    def set_static_param(self, field, value):
        self.static_params[field] = value 

    def set_dynamic_param(self, field, value):
        self.dynamic_params[field] = value

    def set_url(self, extension):
        self.url = os.path.join(self.base_url, extension)
    
    def set_method(self, method):
        self.method = method.upper()

    def call_api(self):
        params = self.static_params.copy()
        params.update(self.dynamic_params)

        try:
            req = requests.request(self.method, self.url, params=params, auth=self.auth, files=self.file)
            res = (req.status_code, req.content)
        except Exception as e:
            res = (-1, e)
        self.dynamic_params = {}
 
        return res

    def find_objects_by_id(self, ident, fields=["pid"], **kwargs):
        """Find object by searching for identifier."""
        # Returns xml of objects.
        self.set_url("objects")
        self.set_dynamic_param("query", "identifier~{0}".format(ident))
        for f in fields:
            self.set_dynamic_param(f, "true")
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        self.set_dynamic_param("pid", "true")
        return self.call_api()

    def find_objects(self, term, fields=["pid"]):
        """Use findObjects API call with the "terms" argument."""
        self.set_url("objects")
        self.set_dynamic_param("terms", term)
        for f in fields:
            self.set_dynamic_param(f, "true")
        self.set_dynamic_param("pid", "true")
        return self.call_api()

    def resume_find_objects(self, term, token, fields=["pid"]):
        """Use token to resume getting results from previous search."""
        self.set_url("objects")
        self.set_dynamic_param("terms", term)
        self.set_dynamic_param("sessionToken", token)
        for f in fields:
            self.set_dynamic_param(f, "true")
        self.set_dynamic_param("pid", "true")
        return self.call_api()

    def get_datastream(self, pid, dsid, **kwargs):
        """Get datastream according to pid and ds id.

        Returns: data about the datastream, not the content itself. See: get_datastream_dissemination.
        """
        self.set_url("objects/{0}/datastreams/{1}".format(pid, dsid))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        return self.call_api()

    def get_datastream_dissemination(self, pid, dsid, **kwargs):
        """Get datastream according to pid and ds id.

        Returns: data about the datastream, not the content itself. See: get_datastream_dissemination.
        """
        self.set_url("objects/{0}/datastreams/{1}/content".format(pid, dsid))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        return self.call_api()

    def get_token(self, xml):
        """Extract token from xml response."""
        xml = etree.fromstring(xml)
        token = xml.find(".//{http://www.fedora.info/definitions/1/0/types/}token")
        if token is not None:
            token = token.text
        return token

    def find_all_objects(self, term, fields=["pid"]):
        """Use resume operation to get all objects matching a given query."""
        all_objects = []
        self.set_dynamic_param("maxResults", "100")
        status, result = self.find_objects(term, fields=fields)
        token = self.get_token(result)
        if status in [200, 201]:
            objects = self.extract_data_from_xml(result)
            all_objects += objects
        while status in [200, 201] and token:
            status, result = self.resume_find_objects(term, token, fields=fields)
            token = self.get_token(result)
            objects = self.extract_data_from_xml(result)    
            all_objects += objects

        return all_objects

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
    def ingest_new(self, namespace, **kwargs):
        """Create new object and generate new pid.
        Returns string of pid on success.

        Allowed kwargs:
        [label] [format] [encoding] [namespace] [ownerId] [logMessage] [ignoreMime] [state]
        """
        self.set_method("POST")
        self.set_url("objects/new")
        self.set_dynamic_param("namespace", namespace)
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        return self.call_api()

    def purge_object(self, pid, logMessage=None):
        """Purge object."""
        self.set_method("DELETE")
        self.set_url("objects/{0}".format(pid))
        if logMessage:
            self.set_dynamic_param("logMessage", logMessage)
        return self.call_api()

    def ingest_at_pid(self, pid, **kwargs):
        """Create new object and generate new pid.
        Returns string of pid on success.

        Allowed kwargs:
        [label] [format] [encoding] [namespace] [ownerId] [logMessage] [ignoreMime] [state]
        """
        self.set_method("POST")
        self.set_url("objects/{0}".format(pid))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        return self.call_api()

    def modify_object(self, pid, **kwargs):
        """Modify existing object.

        Allowed kwargs:
        [label] [ownerId] [state] [logMessage] [\lastModifiedDate]
        """
        self.set_method("PUT")
        self.set_url("objects/{0}".format(pid))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        return self.call_api()
       
    def add_datastream(self, pid, ds_id, filepath, **kwargs):
        """Add datastream to specified object.

        Allowed kwargs:
        [controlGroup] [dsLocation] [altIDs] [dsLabel] [versionable] [dsState] [formatURI] [checksumType] [checksum]
        [mimeType] [logMessage]
        """
        self.set_method("POST")
        self.set_url("objects/{0}/datastreams/{1}".format(pid, ds_id))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        with open(filepath, 'rb') as f:
            self.file = {'file': f}
            res = self.call_api()
        return res

    def update_datastream_content(self, pid, ds_id, file_object, **kwargs):
        """Replace content of specified datastream."""
        self.set_method("POST")
        self.set_url("objects/{0}/datastreams/{1}".format(pid, ds_id))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        self.file = {'file': file_object}
        return self.call_api()

    def modify_datastream(self, pid, ds_id, filepath=None, **kwargs):
        """Modify datastream of specified object.

        Allowed kwargs:
        [controlGroup] [dsLocation] [altIDs] [dsLabel] [versionable] [dsState] [formatURI] [checksumType] [checksum]
        [mimeType] [logMessage]
        """
        self.set_method("PUT")
        self.set_url("objects/{0}/datastreams/{1}".format(pid, ds_id))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        if filepath:
            with open(filepath, 'rb') as f:
                self.file = {'file': f}
                res = self.call_api()
        else:
            res = self.call_api()

        return res

    def purge_datastream(self, pid, ds_id, **kwargs):
        """Purge datastream!"""
        self.set_method("DELETE")
        self.set_url("objects/{0}/datastreams/{1}".format(pid, ds_id))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        return self.call_api()

    def add_relationship(self, pid, predicate, obj, isLiteral=False, datatype=None):
        """Add relationship to RELS-EXT."""
        self.set_method("POST")
        self.set_url("objects/{0}/relationships/new".format(pid))
        self.set_dynamic_param("isLiteral", "true" if isLiteral else "false")
        self.set_dynamic_param("predicate", predicate)
        self.set_dynamic_param("object", obj)
        if datatype and isLiteral:
            dt = self.validate_datatype(datatype)
            if not dt:
                return (-1, "Please provide valid datatype. Allowed types are: int, float, long, dateTime, and double.")     
            self.set_dynamic_param("datatype", dt)
        return self.call_api()

    def delete_relationship(self, pid, predicate, obj, isLiteral=False, datatype=None):
        """Delete relationship in RELS-EXT."""
        self.set_method("DELETE")
        self.set_url("objects/{0}/relationships".format(pid))
        self.set_dynamic_param("predicate", predicate)
        self.set_dynamic_param("isLiteral", "true" if isLiteral else "false")
        self.set_dynamic_param("object", obj)
        if datatype and isLiteral:
            dt = self.validate_datatype(datatype)
            if not dt:
                return (-1, "Please provide valid datatype. Allowed types are: int, float, long, dateTime, and double.")     
            self.set_dynamic_param("datatype", dt)
        return self.call_api()

    def modify_relationship(self, pid, predicate, obj, new_obj, isLiteral=False, datatype=None):
        self.delete_relationship(pid, predicate, obj, isLiteral=isLiteral, datatype=datatype)
        return self.add_relationship(pid, predicate, new_obj, isLiteral=isLiteral, datatype=datatype)

    def get_relationships(self, pid, format="n-triples", predicate=None):
        """Return all relationship associated with given pid, limited by predicate if supplied."""
        self.set_url("objects/{0}/relationships".format(pid))
        self.set_dynamic_param("format", format)
        if predicate:
            self.set_dynamic_param("predicate", predicate)
        return self.call_api()

    def get_next_pid(self, namespace):
        """Get next available pid from within given namespace."""
        self.set_method("POST")
        self.set_url("objects/nextPID")
        self.set_dynamic_param("namespace", namespace)
        self.set_dynamic_param("format", "xml")
        return self.call_api()

    def get_object_profile(self, pid):
        """Get details about a given object."""
        self.set_url("objects/{0}".format(pid))
        self.set_dynamic_param("format", "xml")
        return self.call_api()

    def list_datastreams(self, pid):
        """List datastreams for given object."""
        self.set_url("objects/{0}/datastreams".format(pid))
        self.set_dynamic_param("format", "xml")
        return self.call_api()

    def validate_datatype(self, datatype):

        dt = [d for d in self.valid_datatype_uris if datatype == d or datatype == d.split("#")[1]] 
        if dt:
            return dt[0]
        return None


