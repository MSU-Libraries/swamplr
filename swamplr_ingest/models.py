from __future__ import unicode_literals

from django.db import models

# Create your models here.

class ingest_jobs(models.Model):
    """Information needed to start ingest-specific jobs."""
    ingest_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    source_dir = models.CharField(max_length=255)
    # The collection name determines the particular ingest class created for the job.
    collection_name = models.CharField(max_length=255)
    namespace = models.CharField(max_length=255)
    replace_on_duplicate = models.CharField(max_length=1)
    process_new = models.CharField(max_length=1)
    process_existing = models.CharField(max_length=1)
    subset = models.IntegerField(default=0)
    rels_ext_from_file = models.CharField(max_length=1)
    rels_ext_generated = models.CharField(max_length=1)

class delete_jobs(models.Model):
    """Delete objects."""
    delete_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    source_job = models.ForeignKey('ingest_jobs')

class delete_objects(models.Model):
    """Each object deleted."""
    object_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    # "Success" or "Failure" (or "Skip")
    result_id = models.ForeignKey('object_results')
    pid = models.CharField(max_length=64, null=True)
    deleted = models.DateTimeField(null=True)

class job_datastreams(models.Model):

    job_datastream_id = models.AutoField(primary_key=True)
    ingest_id = models.ForeignKey('ingest_jobs')
    object_type = models.CharField(max_length=32)
    datastream_id = models.ForeignKey('datastreams')

class datastreams(models.Model):
    """Rows for each datastream associated with a given ingest job."""
    datastream_id = models.AutoField(primary_key=True)
    datastream_label = models.CharField(max_length=16)
    # 'y' if a Fedora object, else this is metadata
    is_object = models.CharField(max_length=1)

class job_objects(models.Model):
    """Table to relate filename to PID."""
    object_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    created = models.DateTimeField()
    # Filepath
    obj_file = models.CharField(max_length=255, null=True)
    # "Success" or "Failure" (or "Skip")
    result_id = models.ForeignKey('object_results')
    pid = models.CharField(max_length=64, null=True)
    datastream_id = models.ForeignKey('datastreams')
    new_object = models.CharField(max_length=1, null=True)

class object_results(models.Model):

    result_id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=32)

class pathauto_jobs(models.Model):
    """Pathauto job."""
    pathauto_job_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    source_job = models.ForeignKey('ingest_jobs')

class pathauto_objects(models.Model):
    """Each object deleted."""
    object_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    # "Success" or "Failure" (or "Skip")
    result_id = models.ForeignKey('object_results')
    pid = models.CharField(max_length=64, null=True)
    generated = models.DateTimeField(null=True)
