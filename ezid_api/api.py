import re
import os
import requests

class Ezid():

    def __init__(self, base_url = "https://ezid.cdlib.org/", username=None, password=None):
        self.base_url = base_url
        self.url = base_url
        self.method = "GET"
        self.auth = None
        if username and password:
            self.auth = (username, password)
        self.static_params = {}
        self.dynamic_params = {}
        self.headers = {}

    def set_static_param(self, field, value):
        self.static_params[field] = value 

    def set_dynamic_param(self, field, value):
        self.dynamic_params[field] = value

    def set_url(self, extension):
        self.url = os.path.join(self.base_url, extension)

    def get_params_anvl(self):
        params = self.static_params.copy()
        params.update(self.dynamic_params)

        # Code taken from EZID API documentation to escape structural characters from ANVL format guidelines. 
        def escape (s): 
            return re.sub("[%:\r\n]", lambda c: "%%%02X" % ord(c.group(0)), s) 
                     
        anvl = "\n".join("%s: %s" % (escape(name), escape(value)) for name, 
            value in params.items()).encode("UTF-8") 

        return anvl

    def call_api(self):
        data = self.get_params_anvl()
        if data:
            self.headers['content-type'] = "text/plain; charset=UTF-8"           
        try:
            req = requests.request(self.method, self.url, data=data, headers=self.headers, auth=self.auth)
            res = (req.status_code, req.content)
        except Exception as e:
            res = (-1, e.message)
        self.dynamic_params = {}
 
        return res

    def create(self, uid, metadata={}):
        self.method = 'PUT'
        self.set_url('id/{0}'.format(uid))
        for k,v in metadata.items():
            self.set_dynamic_param(k,v)
        return self.call_api()

    def mint(self, namespace, metadata={}):
        self.method = 'POST'
        self.set_url('shoulder/{0}'.format(namespace))
        for k,v in metadata.items():
            self.set_dynamic_param(k,v)
        return self.call_api()

    def get(self, uid):
        self.method ='GET'
        self.set_url('id/{0}'.format(uid))
        return self.call_api()

    def modify(self, uid, metadata):
        self.method = 'POST'
        self.set_url('id/{0}'.format(uid))
        for k,v in metadata.items():
            self.set_dynamic_param(k,v)
        return self.call_api()

    def delete(self, uid):
        self.method ='DELETE'
        self.set_url('id/{0}'.format(uid))
        return self.call_api()


