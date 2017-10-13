import requests
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

    def find_objects_by_id(self, ident, fields=["pid"]):
        """Find object by searching for identifier."""
        # Returns xml of objects.
        self.set_url("objects")
        self.set_dynamic_param("query", "identifier~{0}".format(ident))
        for f in fields:
            self.set_dynamic_param(f, "true")
        self.set_dynamic_param("pid", "true")
        return self.call_api()
       
    def ingest(self, namespace):
        # returns string of pid on success.
        self.set_method("POST")
        self.set_url("objects/new")
        self.set_dynamic_param("namespace", namespace)
        return self.call_api()
       
    def add_datastream(self, pid, ds_id, filepath, **kwargs):
        """Add datastream to specified object.

        kwargs should correspond to parameters passed to the API:
        [controlGroup] [dsLocation] [altIDs] [dsLabel] [versionable] [dsState] [formatURI] [checksumType] [checksum] [mimeType] [logMessage]
        """
        self.set_method("POST")
        self.set_url("objects/{0}/datastreams/{1}".format(pid, ds_id))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        with open(filepath, 'rb') as f:
            self.file = {'file': f}
            res = self.call_api()
        return res

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
    
    def validate_datatype(self, datatype):

        dt = [d for d in self.valid_datatype_uris if datatype == d or datatype == d.split("#")[1]] 
        if dt:
            return dt[0]
        return None
