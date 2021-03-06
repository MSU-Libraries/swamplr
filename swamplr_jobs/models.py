from __future__ import unicode_literals
from django.db import models


class job_messages(models.Model):
    """Traceback and other messages related to job status."""
    message_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    created = models.DateTimeField()
    # The message will take a few forms. Important will be the "traceback" message for failed jobs.
    message = models.TextField(blank=True, null=True)

class job_types(models.Model):
    """Type of each new job, e.g. derivative, ingest, etc."""
    type_id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=64, unique=True)
    app_name = models.CharField(null=True, max_length=64) 


class jobs(models.Model):
    """Primary table storing information on each job created."""
    job_id = models.AutoField(primary_key=True)
    created = models.DateTimeField()
    started = models.DateTimeField(blank=True, null=True)
    completed = models.DateTimeField(blank=True, null=True)
    status_id = models.ForeignKey("status")
    type_id = models.ForeignKey("job_types")
    process_id = models.IntegerField(default=0)
    archived = models.CharField(max_length=1, blank=True)

class status(models.Model):
    """Status of the job: running, failed, successful, etc."""
    status_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=64, blank=True, null=True)
    default = models.CharField(max_length=1)
    failure = models.CharField(max_length=20)
    running = models.CharField(max_length=1)
    success = models.CharField(max_length=1)
