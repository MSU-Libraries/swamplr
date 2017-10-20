## Install and Configure Swamplr

Please note, the following installation instructions have been written to apply to linux servers.

### Install
The site requires a number of non-standard Python libraries to run. These can be installed via aptitude or pip, a
Python-specific package manager. See below for list of dependencies, followed by installation instructions.
 - [Django](https://www.djangoproject.com/): Python web framework required for Swamplr
 - [Requests](http://docs.python-requests.org/en/latest/): HTTP library.
 - [crispy-forms](http://django-crispy-forms.readthedocs.io/en/latest/): Form library, with helpers for django forms and
  bootstrap styling.

```
aptitude install python-pip
pip install django
apt-get install python-mysqldb
aptitude install libxml2-dev libxslt-dev python-dev zlib1g-dev libtiff5-dev libjpeg8-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python-tk
aptitude install python-requests
pip install django-crispy-forms
```

Download the Swamplr application:
```
cd /var/www
mkdir swamplr
chown www-data:www-data swamplr/
sudo -H -u www-data git clone git@git.lib.msu.edu:digital-information/swamplr.git swamplr/
cd swamplr
```

### Configure
To set the necessary configurations, copy the example config file and make modifications to it.

```
cp swamplr_example.cfg swamplr.cfg
vim swamplr.cfg
```

The file contains sections for the database connection information, the allowed hosts, the debug flag, and a secret key.

The database information should match the database created in the previous step that stores the Swamplr data.

The allowed hosts can be a comma separated list of the host names for the Swamplr site. For example, if you host the site at: http://swamplr.example.edu
the allowed host would simply be: swamplr.example.edu.

When the debug flag is set to true, stack trace information will be displayed on the page when an unexpected error occurs.
This setting should not be enabled in a production environment.

The secret key is used internally by Django and should be a random alphanumeric string, which can be created using online key generators.

### Setting up Apache
Install and setup Apache (not part of this documentation).

The Python standard deployment platform for web servers and applications is WSGI. For more information, see the [Django documentation](https://docs.djangoproject.com/en/1.7/howto/deployment/wsgi/). And the Apache module used to host any Python application is called `mod_wsgi`.
```
aptitude install libapache2-mod-wsgi
```

To set up the Django site as a virtual host, create a file called `swmplr.conf` inside `/etc/apache2/sites-available` and include the following text:
```
<VirtualHost *:80>
        ServerName swmamplr.example.edu
        # Include any ServerAlias here as well, for example if the machine has a mirror

        ServerAdmin webmaster@swamplr
        DocumentRoot /var/www/swamplr/swamplr

        # The group name is not related to the server domain name; it's just a label
        WSGIDaemonProcess swamplr.example.edu processes=2 threads=15 display-name=swamplr
        WSGIProcessGroup swamplr.example.edu
        WSGIScriptAlias / /var/www/swamplr/swamplr/wsgi.py

        <Directory /var/www/swamplr/swamplr>
                SetHandler wsgi-script
                DirectoryIndex wsgi.py
                Options +ExecCGI
                <RequireAny>
                    Require ip [LIST OF IPS THAT CAN ACCESS THE SITE]
                    Require local
                </RequireAny>
        </Directory>

        Alias /static/ /var/www/swamplr/eulcom/static/
        <Directory /var/www/swampy/eulcom/static>
                Options -Indexes
                Require all granted
        </Directory>

        ErrorLog ${APACHE_LOG_DIR}/swamplr-error.log
        CustomLog ${APACHE_LOG_DIR}/swamplr-access.log combined
</VirtualHost>
```

Access to the Swamplr site is currently done by IP. Anyone who needs access to the site will need to have their IP added to the list of IPs
on the `Require ip` line above.

WSGI settings can be edited in `wsgi.conf`.
```
cd /etc/apache2/mods-enabled
vim wsgi.conf
```

Under the `WSGIPythonPath` section of the file, add the following lines:
```
WSGIPythonPath /var/www/swamplr
```

Go to `/etc/apache2/sites-enable` and run the following command to enable the site.
```
a2ensite swamplr
```

Restart Apache with:
```
service apache2 restart
```

The Repo Ingest site relies on a MariaDB database stored on a remote database server, that needs to be manually created
before the site will work. Ensure that the connection information matches what was put in the `swamplr.cfg` file.
Provided with the site is a file called manage.py, which can be used to create/update the database structure with the migrate argument.
```
cd /var/www/swamplr
sudo -Hu www-data python manage.py migrate
```

The site should now be available.

### Configuring Cron
TODO -- how to configure the cron jobs

## How to Install & Enable Apps
Currently all of the apps are included in the same code repository as the core Swamplr app, so there are no special steps required to download the code.

The code for each app is located at the top level of the directory structure, at the same level as the core `swamplr_jobs` app.

Since the App is included in the same code repository as the core app, there are no extra steps required to download the code.

The services app does not have any additional depenencies that need to be installed.

To enable an app, edit the settings.py file and add it to the INSTALL_APPS:
```
vim swamplr/settings.py
```

For example, the section of the file when enabling `swamplr_services` would look like:
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

### Services: swamplr_ingest

TODO -- describe any additional install dependencies (apps or server utilities)

TODO -- describe any additional configuration needed (i.e. the json config)

TODO -- describe hint files

### Services: swamplr_services

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
* **run_process**: The base function called when a new job is begun. This function will be passed a job object, and should then proceed to run the given job, providing updates to the database and to the log file where appropriate. The function should return a tuple compopsed of the final status ID and 1 or more messages to be stored in job_messages table.
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

TODO 

```python

```
