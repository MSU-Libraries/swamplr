from django.conf import settings
from time import sleep
from multiprocessing import Process, Value
import multiprocessing
import logging
import os
from swamplr_jobs.models import job_messages, status, jobs
from django.utils import timezone
from models import derivative_files, derivative_results, job_derivatives
import shlex
import subprocess
from pwd import getpwnam
import getpass


#### TODO
#### - fits commands aren't working
#### - mp3 and waveform commands aren't working
#### - occassional MySql server disappeared error (seems better after moving out derive_obj calls)

class Derivatives(object):

    def __init__(self):
        pass

    def start_derivatives(self, derivative_job, derivative_types):
        """Initiate the derivatives job.
        args:
            derivative_job (deriviative job object): job to process
            derivative_types (list of dict): list of the derivative types to process
                allong with their command information
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


        processes = []
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

                    ## loop over each derivative type to be created for each object
                    for derivative in self.derivative_types:

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
                        p = multiprocessing.Process(target=self.create_derivative, args=(self.derivative_job,derive_obj, source_file, derivative, thread_count))
                        processes.append(p)
                        
                        ### update the number of running threads
                        thread_count.acquire()
                        thread_count.value +=1
                        logging.debug("Kicking off thread: {0}".format(thread_count.value))
                        thread_count.release()

                        ### start the process
                        p.start()

        # re-join all the threads to wait until they are complete
        logging.debug("All derivatives queued, waiting for them to finish")
        for p in processes:
            p.join(timeout=60) # TODO move to config?
            # check if process is still running (i.e. it hung and timed out)
            if p.is_alive():
                p.terminate()
                p.join(timeout=2)
                # check if process is still running after being terminated
                if p.is_alive():
                    logging.error("Process {0} still alive after terminate.".format(p.pid))


    def create_derivative(self, derivative_job, derive_obj, source_file, derivative_options, thread_count):
        """Create a derivative for the given object using the command information provided
        args:
            derivative_job (object): the derivative job
            derive_obj (object): the job derivatives object
            source_file (string): file to use as the input to the derivative command
            derivative_options (dict): settings for the command
            thread_count (Syncronized Value): number of threads running
        """
        p = multiprocessing.current_process()

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
            logging.info("(PID={0}) Skipping derivative for {1}".format(p.pid, source_file))
            # mark as skipped in objects table then end the thread
            result_object = derivative_results.objects.get(label="Skipped")
            derivative_files.objects.create(
                job_derive_id=derive_obj,
                created=timezone.now(),
                source_file=source_file,
                target_file=target_file,
                result_id=result_object,
            )

        # create the derivative
        else:
            logging.debug("(PID={0}) Creating derivative for {1}".format(p.pid, source_file))

            # build the command
            # replace all placeholders, output_file, input_file
            if "command" in derivative_options:
                
                command = derivative_options["command"].format(output_file="\"" + target_file + "\"", input_file="\"" + source_file + "\"")
                #logging.debug("command: {0}".format(command))
                args = shlex.split(command)

                # run the command and update the status
                try:
                    output = subprocess.check_output(args)
                    logging.info("(PID={0}) Successfully created derivative at {1}".format(p.pid, target_file))
                    result_object = derivative_results.objects.get(label="Success")
                    derivative_files.objects.create(
                        job_derive_id=derive_obj,
                        created=timezone.now(),
                        source_file=source_file,
                        target_file=target_file,
                        result_id=result_object,
                    )


                except Exception as e:
                    logging.error("(PID={0}) Failed creating derivative at {1}. Error: {2}. Command: {3}".format(p.pid, target_file, e, command))
                    result_object = derivative_results.objects.get(label="Failure")
                    derivative_files.objects.create(
                        job_derive_id=derive_obj,
                        created=timezone.now(),
                        source_file=source_file,
                        target_file=target_file,
                        result_id=result_object,
                    )

                    job_messages.objects.create(
                        job_id=derivative_job.job_id,
                        created=timezone.now(),
                        message= "Error generating derivative to create {0}. Error: {1}. Command: {2}".format(target_file, e, command),
                    )


            else:
                logging.error("(PID={0}) Failed creating derivative at {1}. Error: No command provided in the config file".format(p.pid, target_file))
                result_object = derivative_results.objects.get(label="Failure")
                derivative_files.objects.create(
                    job_derive_id=derive_obj,
                    created=timezone.now(),
                    source_file=source_file,
                    target_file=target_file,
                    result_id=result_object,
                )

                job_messages.objects.create(
                    job_id=derivative_job.job_id,
                    created=timezone.now(),
                    message= "Error generating derivative to create {0}. Error: No command provided in the config file".format(target_file),
                )


        # update the current running thread count to free up another thread
        thread_count.acquire()
        thread_count.value -= 1
        thread_count.release()

