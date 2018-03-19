from __future__ import print_function
from fedora_api.api import FedoraApi
from lxml import etree
import sys



# Must be run from same server as Fedora in swamplr directory.
# Make sure all values below are correct!
# Do not save file with password filled in!


username = "fedoraAdmin"
password = "Awgwg4nPStu?"

id_term = "fa:*"
predicate = "info:fedora/fedora-system:def/model#hasModel"
current_model = "info:fedora/islandora:sp_pdf"
new_model = "info:fedora/islandora:bookCModel"
print("Processing value of {0}".format(predicate))
print("Removing: {0}".format(current_model))
print("Adding: {0}".format(new_model))

f = FedoraApi(username=username, password=password)

status, xml = f.find_objects_by_id(id_term, maxResults=100)

if status == 200:
    tree = etree.fromstring(xml)
    ns = {"f": "http://www.fedora.info/definitions/1/0/types/"}
    objs = tree.xpath("//f:pid", namespaces=ns)
    pids = [o.text for o in objs]
    print("Found {0} objects to process.".format(len(pids)))
    for pid in pids:
        print("Deleting relationship at PID: {0}".format(pid))
        status, result = f.delete_relationship(pid, predicate, current_model)
        
        if status in [200, 201]:
            print("Successfully deleted. Adding new model.")
            status, result = f.add_relationship(pid, predicate, new_model)
            if status in [200, 201]:
                print("Completed successfully: {0}".format(pid))
            else:
                print("Failed to add.")

        else:
            print("Failed to delete.")
else:
    print("Failed to find objects to process.")


