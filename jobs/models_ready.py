from django.db import models
# Create your models here.
from eulfedora.models import DigitalObject, FileDatastream, XmlDatastream, Relation
# from eulxml.xmlmap.mods import MODS
from eulfedora.rdfns import relsext as relsextns
import requests


class FileObject(DigitalObject):
    PDF_CONTENT_MODEL = 'info:fedora/islandora:sp_pdf'
    CONTENT_MODELS = [ PDF_CONTENT_MODEL ]
    file = FileDatastream("OBJ", "Binary datastream", defaults={
            'versionable': True,
    })
    mods = FileDatastream("MODS", "Mods record for this object.", defaults={
            'versionable': True,
    })


class derivative_jobs(models.Model):
    """Table storing data about derivative creation jobs."""
    derive_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('jobs')
    source_type = models.CharField(max_length=64)
    source_dir = models.CharField(max_length=255)
    target_type = models.CharField(max_length=64)
    contrast_value = models.IntegerField()
    brightness_value = models.IntegerField()
    replace_derivatives_flag = models.BooleanField(default=False)
    subset = models.IntegerField(default=0)


class helper_jobs(models.Model):
    """Variety of other 'helping' jobs, including re-index, batch delete, etc."""
    helper_id = models.AutoField(primary_key=True)
    task = models.CharField(max_length=64)
    namespace = models.CharField(max_length=64, blank=True, null=True)
    job_id = models.ForeignKey('jobs', blank=True, null=True)


class ingest_jobs(models.Model):
    """Information needed to start ingest-specific jobs."""
    ingest_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('jobs')
    source_dir = models.CharField(max_length=255)
    # The collection name determines the particular ingest class created for the job.
    collection_name = models.CharField(max_length=255)
    namespace = models.CharField(max_length=255)
    replace = models.BooleanField(default=False)
    ingest_only_new_objects = models.BooleanField(default=False)
    subset = models.IntegerField(default=0)
    datastream = models.CharField(max_length=64)
    datastream_type = models.CharField(max_length=64)


class job_messages(models.Model):
    """Traceback and other messages related to job status."""
    message_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('jobs')
    created = models.DateTimeField()
    # The message will take a few forms. Important will be the "traceback" message for failed jobs.
    message = models.TextField(blank=True, null=True)


class job_objects(models.Model):
    """Table to relate filename to PID."""
    object_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('jobs')
    created = models.DateTimeField()
    # Filepath
    obj_file = models.CharField(max_length=255, blank=True, null=True)
    # "Success" or "Failure" (or "Skip")
    result = models.CharField(max_length=7)


class job_types(models.Model):
    """Type of each new job, e.g. derivative, ingest, etc."""
    type_id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=64)


class jobs(models.Model):
    """Primary table storing information on each job created."""
    job_id = models.AutoField(primary_key=True)
    created = models.DateTimeField()
    started = models.DateTimeField(blank=True, null=True)
    completed = models.DateTimeField(blank=True, null=True)
    status_id = models.ForeignKey("status")
    type_id = models.ForeignKey("job_types")
    process_id = models.IntegerField(default=0)


class object_pids(models.Model):
    """Relates PID to a specific object, which has a status and filename."""
    pid_id = models.AutoField(primary_key=True)
    object_id = models.ForeignKey("job_objects")
    pid = models.CharField(max_length=64)


class status(models.Model):
    """Status of the job: running, failed, successful, etc."""
    status_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=64, blank=True, null=True)
    default = models.CharField(max_length=1)
    failure = models.CharField(max_length=20)
    running = models.CharField(max_length=1)
    success = models.CharField(max_length=1)


