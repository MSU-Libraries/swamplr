# Swamplr

Swamplr is a modular set of tools primarily designed to interact with a Fedora Commons repository ([vers. 3.8](https://wiki.duraspace.org/display/FEDORA38/Fedora+3.8+Documentation)) as well as other components of the Fedora software stack ([Solr](https://lucene.apache.org/solr/guide/), [Gsearch](https://github.com/fcrepo3/gsearch), [Islandora](https://wiki.duraspace.org/display/ISLANDORA/Islandora), etc.)

*Contents:*  
* [Apps](#apps)  
* [Install and Setup](#install-and-setup)
* [Install and Enable Apps](#install-and-enable-apps)
* [System Design](#system-design)  


##  Apps

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
Services is a more generic app that lets users create custom scripts that can be run on a scheduled interval. 
The user specifies the command to run on the server and optionally the user to run it as 
(if not the user specified during the app setup).

Once the `swamplr_services` app is correctly installed and enabled, you should see a new dropdown navigation on the page called "Services".  This dropdown will contain the following items:  

* A list of all your configured services (will not have any be default). Clicking one one of these will queue the service to be run in the "Jobs" page  
* "Manage Services" which allows you to add and remove services

**Manage Services:**  
The top section of the page contains the list of all the services that have already been configured along with information about what they do. Each service will display the following information:  

* Service: The label you identified for the service, which appears in the "Services" dropdown navigation
* Command: The command that will run on the server
* Frequency (mins.): How often the service is configured to run automatically, defaulting to "None" if it does not run automatically
* Last Started: The date and time that the service was last run
* User: The user that should run the command on the server, the default value is set during configuration of the app
* Actions: Available actions for the service. Run will queue the service on the "Jobs" page and "Delete" will remove it from the list of available services

The "Add a Service" section allows you to create a new service command, identifying the following information: 

* Label: Display label for the service
* Description: Longer description for what the service does, for user reference
* Command: The command to run on the server
* Frequency: How often to run the service autoamtically, leave blank for no automated running
* User name: User to run the command, defaulting to what was configured during the app setup

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

