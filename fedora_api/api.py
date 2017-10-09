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

        self.set_method("POST")
        self.set_url("objects/{0}/datastreams/{1}".format(pid, ds_id))
        for f, v in kwargs.items():
            self.set_dynamic_param(f, v)
        with open(filepath, 'rb') as f:
            self.file = {'file': f}
            res = self.call_api()
        return res
