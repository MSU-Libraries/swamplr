# Swamplr

Swamplr is a modular set of tools primarily designed to interact with a Fedora Commons repository ([vers. 3.8](https://wiki.duraspace.org/display/FEDORA38/Fedora+3.8+Documentation)) as well as other components of the Fedora software stack ([Solr](https://lucene.apache.org/solr/guide/), [Gsearch](https://github.com/fcrepo3/gsearch), [Islandora](https://wiki.duraspace.org/display/ISLANDORA/Islandora), etc.)

**Contents:**  
* [Apps](#apps)  
* [Install and Setup](#install-and-setup)
* [Install and Enable Apps](#install-and-enable-apps)
* [System Design](#system-design)  


##  Apps

### Jobs (Core): swamplr_jobs
This is the core Swamplr app. Its purpose is to run and display results from jobs created by other apps. Part of its
design is to have a scheduled task that will run available jobs on a regular interval so that jobs can be scheduled to run
in advance. The job scheduler would be a cron job running at a frequency , which looks for all the jobs that are queued and starts the first queued job.

Once the Jobs app is installed the `Jobs` button appears at the top of the page, clicking on the button will lead you to the `Job Status` page. 

When a new job is scheduled it is displayed on the job page. 

1. The jobs are displayed in the decending order of the `Job ID` , which is the first column on the page. 
    * The job ID is a link which links to additional details of the job . Additions details may vary depending on the type of job
2. The `Job Type` column indicates the type of job. 
    * The job type can be `Ingest` or `Derivatives` or `Services`.
3. The `Details` column prints the most useful information for that job. 
    * `Ingest Jobs` - The `namespace` , `Collection Name` and `Count of successful , failed and skipped` objects are displayed.
    * `Service Jobs`-  The `Service Name` is displayed
4. The `Created` column  prints the time of creation of the job.
5. The `Completed` column prints the time of completion of the job.
6. The `Status` column prints the status of the job.
    * `Job Queued ` - The job is queued and has not yet started (Will not have a completed time).
    * `Running` - The job is running (Will not have a completed time).
    * `Cancelled By User` -  The job is cancelled by the user.
    * `Script error` -  An error has occurred when running the job.
    * `Success`-  The job is completed successfully.
7. The `Actions` column  enables the user to to perform several actions on the job.
    * `Stop Job` -  The user can stop the job before at any time before completion . If the job is stopped the completed time will be the time when the job was terminated.
    * `Remove Job`- The user can remove any completed job . This action removes the job from the display.


Job progress and other relevant information is displayed as each job runs, along with success or failure messages
on completion as applicable.

### Ingest: swamplr_ingest
The ingest app is designed to ingest new content into a Fedora Commons repository. Objects can be uploaded
according to the specifications of individual collections.

**Configuring Collections**

The ingest tool uses collection configuration settings to determine which options to offer the user and
how to process a given ingest job. These collections settings are stored in [collections.json](swamplr_ingest/collections.json)
and [collection_defaults.json](swamplr_ingest/collection_defaults.json). The latter, *default* settings set certain baseline
configurations to be used if not overridden by collection-specific settings. This app includes example collections
used at MSU, but once downloaded can be edited freely.

The default settings file contains content model information for each object type to be ingested. All object
types specified in collection settings **must** also be present here to ensure ingested items are assigned
a content model in the `RELS-EXT` datastream.

```
"content_models": {
  "large_image": {
    "has_model": "info:fedora/islandora:sp_large_image_cmodel"
},

  "compound": {
    "has_model": "info:fedora/islandora:compoundCModel"
},
  "pdf": {
    "has_model": "info:fedora/islandora:sp_pdf"
}
```

The default settings also contain datastream default settings. In the example below, two datastreams are
defined, "TN" and "DATA". The settings in `collection_defaults.json` will be used **unless** these settings are
overwritten in `collections.json`.

```
"datastreams": {
    "TN": {
      "id": "TN",
      "label": "Thumbnail Image",
      "type": "M",
      "versionable": "False",
      "checksum_type": "SHA-512",
      "mimetype": "image/jpeg"
    },
    "DATA": {
      "id": "DATA",
      "label": "Supplemental Data",
      "type": "M",
      "versionable": "False",
      "checksum_type": "SHA-512",
      "mimetype": "application/zip"
    },
```

Collection level settings use the default settings as a basis and overwrite them in cases where the same
configuration appears in both places.
```
"image": {
    "name": "image",
    "label": "Image",
    "type": "default",
    "status": "active",
    "content_model": "large_image",
    "exclude_strings": [],
    "objects": {
        "object": {
            "namespace": "image_test",
            "datastreams": {
                "OBJ": {
                    "marker": [".tif"],
                    "required": "true"
                },
                "TN": {
                    "marker": ["_TN.jpg"],
                    "required": "true"
                }
            },
            "metadata": {
                "DC": {
                    "marker": ["_DC.xml"],
                    "required": "true"
                },
                "MODS": {
                    "marker": ["_MODS.xml"],
                    "required": "true"
                }
            }
        }
    }
},
```
These are the settings for a collection called 'image.' The image
ingest configured here includes "default" as its type setting. The other allowed option is "collection." Any sites
configured with these options will appear in the "Ingest" dropdown menu.

Selecting an ingest option from the dropdown menu should then populate the upload page with options specific to it. The datastream and metadata
options will appear as a set of checkbox options.

The tool will attempt to create an object with each of the selected datastreams and metadata types. Each of these is
configured with a "marker", that is, a string to match within the filename of the file to be uploaded under that datastream's
heading. A warning will appear in the log for any user-selected datastreams that cannot be found in the given object
directory.

A guide to settings:

| Setting | Use |
| ------- | --- |
| top-level key, e.g. "image"   | Name for this ingest type.  |
| name  | Name for this ingest type.   |
| label  | Label to appear on ingest page.   |
| type  | Values may be "default" or "collection"; intended to distinguish between generic content model oriented ingests
   for testing and more well-defined collection oriented settings.|
| status  | If "active" this ingest type will appear in the dropdown menu.   |
| objects  | All object types should be contained here.   |
| object key, e.g. "object"  | Name for object type, default value is simply "object."   |
| content_model  | Should be the name of a content model as it appears in `collection_defaults.json.`   |
| label  | Label to appear on ingest page.   |
| namespace  | Default namespace to use in PID.   |
| datastreams  | All file datastreams to appear on ingest page should be included here.   |
| metadata  | All metadata datastreams to appear on ingest page should be included here.   |

**Directory Structure**

The ingest tool relies on a standard directory structure, wherein a top-level root directory contains
object-level children. For compound or otherwise multi-part objects, child objects should be found as
sub-directories within the main object directory. All files to be ingested should be stored according to this
structure.

For collections that may house a variety of content types, "hint files" can be used to help the algorithm
guess which content model to use for a given object. The hint file should be stored in the object directory
and be named "hint.json" and specify a "type":

```
{
"type": "object"
}
```

The value of "type" should match the name of an object type defined in the collection-level `objects` setting.

The hint file is not needed if only 1 object type is defined, or if 2 object types are defined **and** one of
these is a simple object type and one is a compound object type (i.e. if one of the object types has child objects
and one does not.)

**Specifying Sequence**

The hint file can also be used to extract sequence information for collections
that contain such information within folder names. For this method to work
files should be organized like this:

```
└── dmhsp_root
    ├── AuschwitzBirkenau02
    ├── AuschwitzBirkenau03
    ├── Buchenwald05
```

There *must* be a directory housing the items to be sequenced, named "*_root". This
folder will provide the basis for which the following hint file values will operate:

```
{
"type": "large_image",
 "sequence": "true",
 "filter_by": "sname",
 "sort_by": "snumber",
 "sort_direction": "asc",
 "sort_level": 0,
 "sequence_match": "^(?P<sname>[a-zA-Z]+)(?P<snumber>[0-9.]+)$"
}
```

First, the field "sequence" must be set to "true".

Then, the "sort_level" field should be set to an integer which determines how many
sub-folders down from root to sort: a value of 0 means that the sub-directories of
the root directory itself will be used to apply sorting and sequencing.

This sorting happens by matching each directory to a regular expression pattern, defined in
the "sequence_match" field. In the example above, two pieces of information are extracted
from all matches: an "sname" and a "snumber".

The former is then set as the value for the "filter_by" field. In the example above,
relating to a collection of Holocaust site photographs, the "sname" will be the
camp name, e.g. Buchenwald. All Buchenwald folders will be added to the filter,
then only items in this filter (all those matching the "sname" Buchenwald) are
sorted by "snumber", as per the "sort_by" field.

Both of these pieces of information are added to the RELS-EXT as such:

```
<isSequenceOf xmlns="http://islandora.ca/ontology/relsext#">Buchenwald</isSequenceOf>
<isSequenceNumber xmlns="http://islandora.ca/ontology/relsext#" rdf:datatype="http://www.w3.org/2001/XMLSchema#int">14</isSequenceNumber>
```

The "sort_direction" field can be set to either "asc" or "desc" as desired.

**Ingesting Collections**

Once configured collections can be ingested by submitting the auto-generated form Swamplr will produce.
The form provides options to select the desired namespace for the collection, the source directory in which to find
object folders, and the set of datastreams (either file-like or xml) to be ingested. The only
required datastream is DC (Dublin Core). This datastream should always be selected (and present in object
folders) as it is used to find existing objects in Fedora.

This ability to match existing objects allows for options to manage and update existing Fedora
objects and datastreams. Users can select to process existing objects or to make only new ones,
and from there to either replace existing datastreams, or ignore them.

The job dashboard will update with progress as it crawls through the files in the supplied directory,
considering them either to be successes (some change to the object was successfully made), failures (the
desired change was not completed satisfactorily, in at least one of its components), or skips (in which
the object is not touched).

The job detail page provides correspondence between the filesystem and the Fedora Commons object, as well
as important messages generated along the way. For debugging it will still be necessary to consult
the log file set up during configuration of the Apache server.



### Services: swamplr_services
Services is a more generic app that lets users create custom scripts that can be run on a scheduled interval. 
The user specifies the command to run on the server and optionally the user to run it as 
(if not the user specified during the app setup).

Once the `swamplr_services` app is correctly installed and enabled, you should see a new dropdown navigation on the page called "Services".  This dropdown will contain the following items:  

* A list of all your configured services (will not have any be default). Clicking one one of these will queue the service to be run in the "Jobs" page  
* "Manage Services" which allows you to add and remove services

**Manage Services:**  
The top section of the page contains the list of all the services that have already been configured along with information about what they do. Each service will display the following information:  

* `Service`: The label you identified for the service, which appears in the "Services" dropdown navigation
* `Command`: The command that will run on the server
* `Frequency (mins.)`: How often the service is configured to run automatically, defaulting to "None" if it does not run automatically
* `Last Started`: The date and time that the service was last run
* `User`: The user that should run the command on the server, the default value is set during configuration of the app
* `Actions`: Available actions for the service. Run will queue the service on the "Jobs" page and "Delete" will remove it from the list of available services

The "Add a Service" section allows you to create a new service command, identifying the following information: 

* `Label`: Display label for the service
* `Description`: Longer description for what the service does, for user reference
* `Command`: The command to run on the server
* `Frequency`: How often to run the service autoamtically, leave blank for no automated running
* `User name`: User to run the command, defaulting to what was configured during the app setup

**Writing Service Commands:**

For the core jobs app to know if a given command succedes or fails, it checks the return code. Zero for success and non-zero for failure. Any message that is printed from the command will be included in the job messages. Here is a sample command script that will check if a service is running on the server: 

```
#!/bin/bash
RETURN_CODE=2
SERVICE_PATH=${1:-/var/run/apache2/apache2.pid}
if [[ -f $SERVICE_PATH ]]; then
    SERVICE_PID=$(cat $SERVICE_PATH)
    ps -p $SERVICE_PID > /dev/null
    RETURN_CODE=$?
fi

if [[ $RETURN_CODE -eq 2 ]]; then
    echo "PID file does not exist at: $SERVICE_PATH."
elif [[ $RETURN_CODE -eq 1 ]]; then
    echo "PID $SERVICE_PID is not running."
elif [[ $RETURN_CODE -eq 0 ]]; then
    echo "Process running at: $SERVICE_PID."
else
    echo "Unexpected return code: $RETURN_CODE for PID $SERVICE_PID."
fi
exit $RETURN_CODE
```

This is saved in a file called `check_service.sh`. Make sure that the user you want to run the script has appropriate permissions to do so. 

To break down what this script does:
* Determines the path to the service's PID file based on the paremeter to the script, defaulting to Apache's PID file
* If the PID file exists, check the status of the PID within that file on the server to see if the process is running and set the return code accordingly
* If the return code is 2 (what it was set to at the begining) then the message to return is that the PID file did not exist
* If the return code was 1 then the service was not running
* If the return code was 0 then the service was running
* Otherwise there was an unexpected error
* All paths return the error code and display a different message depending on that code

To configure this service in Swamplr, Create a new service giving it a name, description and frequency. Then for the command provide: `/path/to/check_services.sh path/to/service.pid` and add the service. 

Afer you add the service, click "Run" to have it do a test run and you can now check the status of the run through the "Jobs" page.

Some other examples of services you could write would be for restarting services, so users would not need SSH access to your service in order to do so. Or even custom test scripts to verify various components of your server setup (from Fedora Commons to Solr or even you repository's front end web-site).

## Install and Setup

See the [install instructions](INSTALL.md) for detailed steps to install and configure the application.  

## Install and Enable Apps

See the [install instructions](INSTALL.md#how-to-install-enable-apps) for detailed steps to install and configure specific apps.   

## System Design

See the [system design](INSTALL.md#system-design) for details on the database and app structures.  

