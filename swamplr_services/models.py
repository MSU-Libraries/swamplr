from __future__ import unicode_literals

from django.db import models

class services(models.Model):

    service_id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=32)
    description = models.CharField(max_length=1024, null=True)
    command = models.CharField(max_length=1024)
    run_as_user = models.CharField(max_length=16, null=True)
    frequency = models.BigIntegerField(null=True)
    last_started = models.DateTimeField(null=True)

class service_jobs(models.Model):

    job_id = models.OneToOneField("swamplr_jobs.jobs", primary_key=True, on_delete=models.CASCADE) 
    service_id = models.ForeignKey("services")

class service_status(models.Model):

    service_status_id = models.OneToOneField("swamplr_jobs.status", primary_key=True, on_delete=models.CASCADE) 
    status = models.CharField(max_length=32)
