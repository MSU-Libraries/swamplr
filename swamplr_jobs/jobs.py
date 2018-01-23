from django.utils import timezone
import os
from models import *
import logging


class JobQueue():
    """Class to handle read and write access to the jobs database..

    The eulcom_jobs table is an important table that holds the job_id which is connected
    to the other tables in the database.
    """

    def __init__(self):
        """Initialize class."""
        pass
    
    @staticmethod
    def get_jobs(job_type="all", job_status="active"):
	"""Get all jobs matching selected filters."""
        # TODO - add filters.
        
        job_data = jobs.objects.all().order_by('-created')
        current_jobs = {}
        
        for job in job_data:

            currjobData = {}
            currjobData['job_id'] = job.job_id
            currjobData['status'] = status.objects.get(status_id=job.status_id_id).status
            currjobData['type'] = job_types.objects.get(type_id=job.type_id_id).label
            currjobData['started'] = job.started
            currjobData['completed'] = job.completed
            currjobData['success_count'] = get_job_status_count(job.job_id, "success") 
            currjobData['failed_count'] = get_job_status_count(job.job_id, "failure") 
            currjobData['skipped_count'] = get_job_status_count(job.job_id, "skipped") 
        
            current_jobs[job.job_id] = currjobData
        
        return current_jobs
        

    @staticmethod
    def get_length(path):
        """Count directories in top-level collection dir.

        args:
            path(str): path to files to tally
        """
        root_dir = JobQueue.get_root_dir(path)
        if any(f.endswith(".xml") for f in os.listdir(root_dir)):
            length = 1
        else:
            length = len(os.listdir(root_dir))
        return length

    @staticmethod
    def get_root_dir(path):
        """Find root directory, which should end in _root.

        args:
            path(str): path to files to tally
        """
        root_dir = path
        for root, dirs, files in os.walk(path):
            for dirx in dirs:
                if dirx.endswith("_root"):
                    root_dir = os.path.join(root, dirx)
                    break

        return root_dir

    @staticmethod
    def update_jobs_db(job_id, status_id, flag):
        """ Updates the database tables corresponding to the job_id

        args:
            job_id(int):  job_id of a queued job
            status_id(int):  status_id is the id from the eulcom_status table . It is the current state the job is in
            flag(str): Determines if the job is started or completed

        """

        if flag == "started":
            # getting the process id for the job
            process_id = os.getpid()
            started_timestamp = timezone.now()
            jobs.objects.filter(job_id=job_id).update(status_id=status_id, started=started_timestamp, process_id=process_id)

        elif flag == "completed":
            completed_timestamp = timezone.now()
            jobs.objects.filter(job_id=job_id).update(status_id=status_id,
                                                      completed=completed_timestamp)
        logging.info("{0} job at {1}".format(flag.title(), job_id))

    @staticmethod
    def insert_jobs_db(status_id, type_id, collection_name, namespace, src_dir, replace,
                       ingest_only_new_objects, subset, datastreams, metadata):
        """Inserts an ingest job for the first time into the database.

        Inserts a row into the eulcom_ingest_jobs table for every datastream (both file and metadata) to be processed.

        args:
            status_id(int): status_id is the id from the eulcom_status table. It is the current state the job is in
            type_id(int): type_id is the id from the eulcom_job_type table.
                It's used to determine if the job is of the type ingest, derivative or indexing.
            collection_name(str): The collection name  eg: DMHSP
            namespace(str): the pid namespace
            src_dir(str): the source directory
            replace_metadata(bool): Check if the replace_metadata flag is true or false
            ingest_only_new_objects(bool): Check if the ingest_only_new_objects flag is true or false
            subset(Int): the subset of objects that needs to be ingested . 0 if it is not entered
            datastreams: datastreams to process
            metadata: metadata types to process
        """
        # Get status of job.
        status_object = status.objects.get(status_id=status_id)

        # Get type of job.
        job_types_object = job_types.objects.get(type_id=type_id)

        # Create a new generic job including time created.
        created = timezone.now()
        insert_jobs = jobs.objects.create(
            created=created, status_id_id=status_object.status_id,
            type_id_id=job_types_object.type_id
        )
        insert_jobs.save()

        # Create row for each type of metadata and file datastream to create.
        if datastreams is not None:
            all_datastreams = datastreams + metadata
            print("all_datastreams")
            print(all_datastreams)
            for ds_name, ds_type in all_datastreams:
                ingest_jobs.objects.create(
                    job_id_id=insert_jobs.job_id, source_dir=src_dir,
                    collection_name=collection_name, namespace=namespace,
                    replace=replace,
                    ingest_only_new_objects=ingest_only_new_objects, subset=subset,
                    datastream=ds_name, datastream_type=ds_type,
                )

        else:
            ingest_jobs.objects.create(
                job_id_id=insert_jobs.job_id, source_dir=src_dir,
                collection_name=collection_name, namespace=namespace,
                replace=replace,
                ingest_only_new_objects=ingest_only_new_objects, subset=subset,
                datastream="Null"
            )

        logging.info("Inserted {1} job {0} into database.".format(insert_jobs.job_id, job_types_object.label))

    @staticmethod
    def insert_derivative_jobs_db(status_id, type_id, der_kwargs, collection_type, path, length, contrast_val, brightness_val, replace_derivatives, subset):
        """Inserts an derivative job for the first time into the database . Inserts a row into the eulcom_derivative_jobs table for every derivative type

        args:
            status_id(int): status_id: status_id is the id from the eulcom_status table . It is the current state the job is in
            type_id(int): type_id: type_id is the id from the eulcom_job_type table . It is used to determine if the job is of the type ingest, derivative or indexing
            der_kwargs(dict): dictionary of the selected derivative types
            collection_name(str): Detrmines if it it is an image derivative or a pdf derivative
            path(str): The source path of the directory
            contrast_val(int): Desired contrast value of the derivative
            brightness_val(int): Desired brightness value of the derivative
            replace_derivatives(bool): Check if the replace_derivatives flag is true or false
            subset(Int): the subset of objects that needs to be process . 0 if it is not entered
        """
        status_object = status.objects.get(status_id=status_id)
        job_types_object = job_types.objects.get(type_id=type_id)
        created = timezone.now()
        insert_jobs = jobs.objects.create(created=created, status_id_id=status_object.status_id,
                                                           type_id_id=job_types_object.type_id)
        insert_jobs.save()
        current_job = jobs.objects.order_by("job_id").last()
        for type, value in der_kwargs.iteritems():
            derivative_jobs.objects.create(job_id_id=current_job.job_id, source_type=collection_type,
                                                            source_dir=path, target_type=type, contrast_value=contrast_val, brightness_value=brightness_val, replace_derivatives_flag=replace_derivatives, subset=subset )
        logging.info("Inserted {0} job {1} into database.".format(job_types_object.label, current_job.job_id))


    @staticmethod
    def insert_index_jobs(status_id, type_id, namespace):
        """Inserts an Index job for the first time into the database . Inserts a row into the eulcom_helper_jobs table for every derivative type

        args:
            status_id(int): status_id: status_id is the id from the eulcom_status table . It is the current state the job is in
            type_id(int): type_id: type_id is the id from the eulcom_job_type table . It is used to determine if the job is of the type ingest, derivative or index
            namespace(str): namespace of the job that is queued for reindexing

        """
        created = timezone.now()
        insert_jobs = jobs.objects.create(created=created, status_id_id=status_id,
                                                           type_id_id=type_id)
        current_job = jobs.objects.order_by("job_id").last()
        helper_jobs.objects.create(task="reindex", namespace = namespace, job_id_id = current_job.job_id)

        logging.info("Inserted Index job at {0}".format(current_job.job_id))

    @staticmethod
    def cancel_ingest_jobs(job_id):
        """Cancels an ingest job

        args:
            job_id(int): job_id of the ingest job that needs to be cancelled
        """
        status_obj = status.objects.get(status="Cancelled By User")
        status_id = status_obj.status_id #status for Cancelled by user
        jobs.objects.filter(job_id=job_id).update(status_id=status_id)


    @staticmethod
    def insert_job_objects(job_id, file_path, result):
        """ Inserts the objects into eulcom_job_objects table

        args:
            job_id(int): Every object is associated with the corresponding job_id
            file_path(str): Path of the object
            result(str): determines status of the job for that object
        """
        created = timezone.now()
        jobObject =  jobs.objects.get(job_id=job_id)
        statusObj = status.objects.get(status_id=jobObject.status_id_id)
        if statusObj.status == "Cancelled By User":
            try:
                # Raise an exception with argument
                raise ValueError('This job was manually canceled.')
            except Exception:
                 # Catch exception
                 logging.info("Job Canceled by user")
                 os._exit(1)
        else :
            job_objs = job_objects.objects.create(job_id_id=job_id, created=created, obj_file=file_path,
                                                               result=result)
            logging.info("Handling job id {0}".format(job_id))


    @staticmethod
    def insert_object_pids(job_id, pid):
        """Inserts the pids into eulcom_object_pids table

         args:
            job_id(int): Every object is associated with the corresponding job_id
            pid(str): pid of the object

        """

        job_object = job_objects.objects.filter(job_id_id = job_id).last()
        object_pids.objects.create(object_id_id=job_object.object_id, pid=pid)
        logging.debug("Inserted into eulcom_object_pids")


    @staticmethod
    def insert_job_messages(job_id, job_message):
        """Inserts the job messages into eulcom_job_messages table

         args:
            job_id(int): Every object is associated with the corresponding job_id
            job_message(str): Failure message for the job
        """

        status_obj = status.objects.get(failure="error")
        jobs.objects.filter(job_id=job_id).update(status_id=status_obj.status_id,
                                                                   completed=timezone.now())
        job_messages.objects.create(job_id_id=job_id, created=timezone.now(), message=job_message)
        logging.debug("Inserted into eulcom_job_messages")
