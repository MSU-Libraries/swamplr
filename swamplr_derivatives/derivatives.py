from django.conf import settings
from time import sleep
from multiprocessing import Process, Value
import multiprocessing
import logging
import os
from swamplr_jobs.models import job_messages, status, jobs
from proclr import PChain
from django.utils import timezone
from models import derivative_files, derivative_results, job_derivatives
import subprocess
from pwd import getpwnam
import getpass
from django import db


class Derivatives(object):

    def __init__(self):
        pass

    def start_derivatives(self, derivative_job, derivative_types):
        """Initiate the derivatives job.
        args:
            derivative_job (deriviative job object): job to process
            derivative_types (list of dict): list of the derivative types
                along with their command information
        """
        self.derivative_job = derivative_job
        self.derivative_types = derivative_types

        job_messages.objects.create(
            job_id=derivative_job.job_id,
            created=timezone.now(),
            message="Initializing Derivative Job."
        )

        # Get the types specified in the job
        derivative_job_types = job_derivatives.objects.filter(derive_id = self.derivative_job)
        types = [d.derive_type for d in derivative_job_types]
        output_endings = [d["output_file"].replace("{0}","") for d in self.derivative_types]

        # filter the config settings based on only the selected derivatives for this job
        self.derivative_types = [d for d in self.derivative_types if d['derivative_type'] in types]

        # get the job_derivative objects for each of the types
        derive_objs = {}
        for derivative in self.derivative_types:
            try:
                derive_obj = job_derivatives.objects.get(derive_id=self.derivative_job,
                    derive_type=derivative["derivative_type"])
                derive_objs[derivative["derivative_type"]] = derive_obj
            except Exception as e:
                # TODO -- why does it fall in this when the record does exist in the db??
                # only seems to fall into it sometimes, not consistantly
                logging.error("Could not find job_derivatives object for {0}, {1} in DB.".format(self.derivative_job.derive_id,derivative["derivative_type"]))
                continue

        # get the 3 status objects to pass to the threads (success, fail, skip)
        status_objs = {}
        try:
            status_objs['skipped'] = derivative_results.objects.get(label="Skipped")
            status_objs['success'] = derivative_results.objects.get(label="Success")
            status_objs['failure'] = derivative_results.objects.get(label="Failure")
        except Exception as e:
            logging.error("Could not find all 3 status objects in the database.")
            raise 


        processes = []
        thread_index = 0
        files_processed = 0
        thread_count = Value('i',0)
        # walk the directory starting at the source_dir
        for root, dirs, files in os.walk(self.derivative_job.source_dir):
            for f in files:
                ## determine if file matches the source_ext, skip if not
                if f.endswith('.'+self.derivative_job.source_file_extension.lower()):

                    ## if the file matches the output file format, skips since this file is a derivative
                    source_file = os.path.join(root, f)
                    if f.endswith(tuple(output_endings)):
                        #logging.debug("Not processing {0}, since this file is a derivative.".format(source_file))
                        continue
                    ## check if over the subset count; if so, break
                    if self.derivative_job.subset is not None and self.derivative_job.subset > 0 and files_processed >= self.derivative_job.subset:
                        logging.debug("Reached subset count ({0}), stopping processing.".format(files_processed))
                        break

                    ## check if the job has been canceled -- TODO

                    ## loop over each derivative type to be created for each object
                    for derivative in self.derivative_types:
                        thread_index += 1
                        ### if we are over the max thread count, wait until one frees up
                        if thread_count.value >= settings.MAX_THREADS:
                            while thread_count.value >= settings.MAX_THREADS:
                                logging.debug("{0} threads running, waiting before continuing processing".format(thread_count.value))
                                sleep(3)

                        ### get the derive object
                        try:
                            derive_obj = derive_objs[derivative["derivative_type"]]
                        except Exception as e:
                            logging.error("Could not find job_derivatives object for {0}, {1}.".format(self.derivative_job.derive_id,derivative["derivative_type"]))
                            continue

                        ### create a process for create_derivative for the object and derivative type
                        p = multiprocessing.Process(target=self.create_derivative, args=(self.derivative_job,derive_obj, source_file, derivative, status_objs, thread_count, thread_index))
                        processes.append(p)
                        
                        ### update the number of running threads
                        thread_count.acquire()
                        thread_count.value +=1
                        logging.debug("Kicking off thread: {0}".format(thread_count.value))
                        thread_count.release()

                        ### start the process
                        db.connections.close_all()
                        p.start()

                    ## increment number of files processed
                    files_processed += 1
            ## check if over the subset count; if so, break
            if self.derivative_job.subset is not None and self.derivative_job.subset > 0 and files_processed >= self.derivative_job.subset:
                break


        # re-join all the threads to wait until they are complete
        logging.debug("All derivatives queued, waiting for them to finish")
        for p in processes:
            p.join(timeout=120) # TODO move to config?
            # check if process is still running (i.e. it hung and timed out)
            if p.is_alive():
                logging.debug("Thread {0} still alive after timeout limit, terminating.".format(thread_index))
                p.terminate()
                p.join(timeout=2)
                # check if process is still running after being terminated
                if p.is_alive():
                    logging.error("Thread {0} still alive after terminate.".format(thread_index))


    def create_derivative(self, derivative_job, derive_obj, source_file, derivative_options, status_objs, thread_count, thread_index):
        """Create a derivative for the given object using the command information provided
        args:
            derivative_job (object): the derivative job
            derive_obj (object): the job derivatives object
            source_file (string): file to use as the input to the derivative command
            derivative_options (dict): settings for the command
            status_objs (dict): the 3 result status objects (success, failure, skipped)
            thread_count (Syncronized Value): number of threads running
            thread_index(int): increment threads opened during the course of the current job.
        """
        try:
            # make sure the source_file exists
            if not os.path.isfile(source_file):
                message = "Source file no longer exists on the filesystem. Can not process. {0}".format(source_file)
                logging.error(message)
                job_messages.objects.create(
                    job_id=derivative_job.job_id,
                    created=timezone.now(),
                    message= message,
                )

            # determine the target file
            ext = "." + source_file.split(".")[-1]
            target_file = derivative_options["output_file"].format(source_file.replace(ext,""))

            # check if the target_file exists, skip if replace = false
            ext = "." + source_file.split(".")[-1]
            if os.path.isfile(target_file) and not derivative_job.replace_on_duplicate:
                logging.info("(THREAD={0}) Skipping {1} derivative for {2}".format(thread_index, derive_obj.derive_type, source_file))
                # mark as skipped in objects table then end the thread
                #result_object = derivative_results.objects.get(label="Skipped")
                derivative_files.objects.create(
                    job_derive_id=derive_obj,
                    created=timezone.now(),
                    source_file=source_file,
                    target_file=target_file,
                    result_id=status_objs['skipped'],
                )

            # create the derivative
            else:
                logging.debug("(THREAD={0}) Creating {1} derivative for {2}".format(thread_index, derive_obj.derive_type, source_file))

                # build the command
                # replace all placeholders, output_file, input_file, brightness, contrast
                brightness= derivative_job.brightness if derivative_job.brightness is not None else 0
                contrast = derivative_job.contrast if derivative_job.contrast is not None else 0

                pchain = PChain()
                
                for command in derivative_options["commands"]:
                    c = command[0].format(output_file="\"" + target_file + "\"", input_file="\"" + source_file + "\"", brightness=brightness, contrast=contrast)
                    logging.debug("(THREAD={0}) Adding command: {1}. JOIN: {2} ({3})".format(thread_index, c, command[1], getattr(pchain, command[1])))
                    pchain.add(c, getattr(pchain, command[1]))
                    
                exit_code = pchain.run()    

                # run the command and update the status
                if exit_code == 0:
                    logging.info("(THREAD={0}) Successfully created {1} derivative at {2}".format(thread_index, derive_obj.derive_type, target_file))
                    #result_object = derivative_results.objects.get(label="Success")
                    derivative_files.objects.create(
                        job_derive_id=derive_obj,
                        created=timezone.now(),
                        source_file=source_file,
                        target_file=target_file,
                        result_id=status_objs['success'],
                    )

                elif exit_code is None or len(derivative_options["commands"]) == 0:
                    logging.error("(THREAD={0}) Failed creating {1} derivative at {2}. Error: {2}.".format(thread_index, derive_obj.derive_type, target_file, "No commands supplied."))
                    #result_object = derivative_results.objects.get(label="Failure")
                    derivative_files.objects.create(
                        job_derive_id=derive_obj,
                        created=timezone.now(),
                        source_file=source_file,
                        target_file=target_file,
                        result_id=status_objs['failure'],
                    )

                    job_messages.objects.create(
                        job_id=derivative_job.job_id,
                        created=timezone.now(),
                        message= "Error generating {0} derivative to create {1}. Error: {2}.".format(derive_obj.derive_type, target_file, "No commands supplied."),
                    )


                else:
                    logging.error("(THREAD={0}) Failed creating {1} derivative at {2}. Error: {3}".format(thread_index, derive_obj.derive_type, target_file, pchain.stderr()))
                    #result_object = derivative_results.objects.get(label="Failure")
                    derivative_files.objects.create(
                        job_derive_id=derive_obj,
                        created=timezone.now(),
                        source_file=source_file,
                        target_file=target_file,
                        result_id=status_objs['failure'],
                    )

                    job_messages.objects.create(
                        job_id=derivative_job.job_id,
                        created=timezone.now(),
                        message= "Error generating {0} derivative to create {1}. Error: {2}".format(derive_obj.derive_type, target_file, pchain.stderr()),
                    )

        except Exception as e:
            logging.error("(THREAD={0}) Unexpected error occured in thread generating {1} derivative for {2}. {3}.".format(thread_index,derive_obj.derive_type, source_file, e))
            # Not attempting to log the object as failed in case that was where the exception occured
        finally:
            # update the current running thread count to free up another thread
            thread_count.acquire()
            thread_count.value -= 1
            thread_count.release()
            logging.debug("(THREAD={0}) COMPLETE. creating {1} derivative for {2}".format(thread_index, derive_obj.derive_type, source_file))


