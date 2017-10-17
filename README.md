# Swamplr

Swamplr is a modular set of tools primarily designed to interact with a Fedora Commons repository ([vers. 3.8](https://wiki.duraspace.org/display/FEDORA38/Fedora+3.8+Documentation)) as well as other components of the Fedora software stack ([Solr](https://lucene.apache.org/solr/guide/), [Gsearch](https://github.com/fcrepo3/gsearch), [Islandora](https://wiki.duraspace.org/display/ISLANDORA/Islandora), etc.)

*Contents:*  
* [Available Apps](#available-apps)  
* [Install and Setup](#install-and-setup)
* [Install and Enable Apps](#install-and-enable-apps)
* [System Design](#system-design)  


## Available Apps

### Jobs (Core): swamplr_jobs
This is the core Swamplr app. Its purpose is to run and display results from jobs created by other apps. Part of its
design is to have a scheduled task that will run available jobs on a regular interval so that jobs can be scheduled to run
in advance. Job progress and other relevant information is displayed as each job runs, along with success or failure messages
on completion as applicable.

### Ingest: swamplr_ingest
An app designed to ingest new content into a Fedora Commons repository.

### Derivatives: swamplr_derivatives
An app that creates various derivatives for files that are to be ingested. The types of derivatives that are available to be generated are based on the type of content, for example images have options like creating a JPG, TIF and JP2. But audio objects have options to create waveforms preview images.  

### Services: swamplr_services
A more generic app that lets users create custom scripts that can be run on a scheduled interval. The user specifies the
command to run on the server and optionally the user to run it as (if not the same user that runs Swamplr).

## Install and Setup


#### Swamplr Ingest

The site should now be available. 


## Install and Enable Apps
Currently all of the apps are included in the same code repository as the core Swamplr app, so there are no special steps required to download the code.

The code for each app is located at the top level of the directory structure, at the same level as the core `swamplr_jobs` app.

### Services: swamplr_services
Since the App is included in the same code repository as the core app, there are no extra steps required to download the code.

The services app does not have any additional depenencies that need to be installed.

To enable the app, edit the settings.py file and add it to the INSTALL_APPS:
```
vim swamplr/settings.py
```

That section of the file should now look like:
```
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'swamplr_jobs',
    'swamplr_services',
)
```

There may be some additional items in that section if you have already enabled other apps. 

The configurations for the services app is in the `swamplr_services/apps.py` file.
```
class ServicesConfig(AppConfig):
    name = 'swamplr_services'
    run_as_user = 'root'
```
The `name` should not be changed, as that is just the name of the app.  
The `run_as_user` is the user that will be used to run services as in the event one is not provided by the user when adding a service.  


## System Design
### Technologies

Swamplr is built in [Django](https://www.djangoproject.com/), a Python-based web development framework, and is comprised of a set of interrelated modules, or "apps." The core Swamplr application runs swamplr_jobs, a job-queuing system for handling jobs created by a set of other apps, such as swamplr_services, swamplr_ingest, and swamplr_derivatives. 

### App Structure

Each Swamplr app must include a set of features that allows it to interface with the jobs app specifically, and with the Django API generally. Creating a new Django app with the command
```
# 'Compound' content models are those with hierarchical directory structures.
self.compound_content_models = ["compound", "newspaper_issue", "book"]
self.simple_content_models = ["large_image", "pdf", "newspaper_page", "oral_histories", "audio"]
```


**Hint Files**

View functions can return static HTML or, more dynamically, a *template* and a *context*. The template consists of HTML with Django template language mixed in, while the context contains variables to apply in the specified template. See the [Django documentation](https://www.djangoproject.com/) for a thorough explanation of the structure and functionality of a Django project. 

### Core Database Tables

The core app, swamplr_jobs, will control a jobs database tables which additional apps will populate with jobs. The tables in the database organize jobs according to type, and store status and error information for each job. Brief descriptions below, and see the (#TODO) database schema document for more information:

* **jobs**: Covers jobs, status, start and end times, and job type.
* **status**: List of possible job statuses.
* **job_types**: Stores available job types.
* **job_messages**: Error messages and traceback for failed jobs.
* **job_objects**: Granular tracking of the file objects a given job has acted on, if any.

### App Connections

Each app connects to the larger Django project which runs it. The project's settings.py file contains basic configurations that control the database connection, handling of templates, context processors and much more. Meanwhile each app should implement a few basic functions within `views.py` to connect to the jobs queue and to be integrated into the navigation and adminstrative structure of the project.

#### Required Functions

* **get_nav_bar**: Each app's views.py file should have a function to return data for a dropdown menu of functions that looks like this:
```
{
 "label": "",
 "name": "",
 "children": [
     {
      "label": "",
      "id": "",
     },
     ...
  ]
}
```
  * **label**: Text to appear in the heading of the dropdown menu.
  * **name**: The app name, to be used in building links to the app's functionality, e.g. manage-[name], run-[name], etc.
  * **children**: label and id to display in the dropdown menu to connect to functionality.
  

* **manage-[name]**: A function and view that allows users to view/edit the functionality of the app.
* **run_process**: The base function called when a new job is begun. This function will be passed a job object, and should then proceed to run the given job, providing updates to the database and to the log file where appropriate. The function should return a tuple compopsed of the final status ID and 1 or more messages to be stored in job_messages table.
* **pre_process**: The function called before processing of any job begings. This function takes no parameters.
* **get_status_info**: When the job dashboard page or the job detail page is loaded, this function provides data about the job status. It should return two variables, the first containing a list of human readable data to post to the job status page; the second a list (of tuples) containing data about each app-specific data point to be shown on the job detail page.
* **get_actions**: Return list of actions to be loaded on the job status page. Each action should take this form:
```
action = {
    "label": "Stop Job", # the name to display to users.
    "action": "stop_job", # a function name in views.py to be matched to a url.
    "class": "btn-danger", # a class used to style the button, typically a bootstrap button class.
    "args": "job_id", # a string of arguments separated by spaces to be passed to the function set in the 'action' field.
}
```


#### Database Connections

The functionality of individual apps will likely require data updates to newly created tables as well as to the core set of swamplr_jobs tables. This can be handled via Django's [database migrations](https://docs.djangoproject.com/en/1.11/topics/migrations/).

#### URL Handling

Each app will have it's own set of URL configurations. The Django project's urls.py file is set up to direct certain URL patterns to the appropriate app.


```python

```
>>>>>>> ef9e848cb5331b07f589317d3443b1a9b11187ba
