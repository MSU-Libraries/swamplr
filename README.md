
# Swamplr

Swamplr is a modular set of tools primarily designed to interact with a Fedora Commons repository ([vers. 3.8](https://wiki.duraspace.org/display/FEDORA38/Fedora+3.8+Documentation)) as well as other components of the Fedora software stack ([Solr](https://lucene.apache.org/solr/guide/), [Gsearch](https://github.com/fcrepo3/gsearch), [Islandora](https://wiki.duraspace.org/display/ISLANDORA/Islandora), etc.)

## Available Apps

### Jobs (Core): swamplr_jobs
This is the core app that comes re-installed with Swamplr. It's purpose is to run and display results from jobs created by other apps. Part of its design is to have a scheduled task that will run available jobs on a regular interval so it is not up to the individual apps to have to kick them off. It displays the job progress along with relavent information as it runs and success or failure on completion with an error message if applicable. 

### Ingest: swamplr_ingest
An app that allows ingesting new content into a Fedora Commons repository and automatically triggers a Solr reindex of those items.  

### Derivatives: swamplr_derivatives
An app that creates various derivatives for files that are to be ingested. The types of derivatives that are available to be generated are based on the type of content, for example images have options like creating a JPG, TIF and JP2. But audio objects have options to create waveforms preview images.  

### Services: swamplr_services
A more generic app that lets users create custom scripts that can be run on a scheduled interval. The user just has to specify the command to run on the server and optionally the user to run it as (if not the same user that runs Swamplr). 

## How to install and setup Swamplr
TODO

## How to Install & Enable Apps
Currently all of the apps are included in the same code repository as the core Swamplr app, so there are no special steps required to download the code.

The code for each app is located at the top level of the directory structure, at the same level as the core `swamplr_jobs` app.

TODO - describe config changes and any app specific instructions

## System Design
### Technologies

Swamplr is built in [Django](https://www.djangoproject.com/), a Python-based web development framework, and is comprised of a set of interrelated modules, or "apps." The core Swamplr application runs swamplr_jobs, a job-queuing system for handling jobs created by a set of other apps, such as swamplr_services, swamplr_ingest, and swamplr_derivatives. 

### App Structure

Each Swamplr app must include a set of features that allows it to interface with the jobs app specifically, and with the Django API generally. Creating a new Django app with the command
```
python manage.py startapp [appname]
```
creates a directory with Django files including:

* **urls.py**: matches a url to a function in views.py
* **views.py**: contains functions to run in response to matching urls in urls.py; each function returns an HttpResponse object
* **models.py**: contains database table definitions, in Django's database syntax
* **apps.py**: contains the default settings for the app, can be used to offer app-level variables e.g. for urls.py

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


#### Database Connections

The functionality of individual apps will likely require data updates to newly created tables as well as to the core set of swamplr_jobs tables. This can be handled via Django's [database migrations](https://docs.djangoproject.com/en/1.11/topics/migrations/).

#### URL Handling

Each app will have it's own set of URL configurations. The Django project's urls.py file is set up to direct certain URL patterns to the appropriate app.


```python

```
