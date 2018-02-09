# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

class derivative_jobs(models.Model):
    """Information needed to start ingest-specific jobs."""
    derive_id = models.AutoField(primary_key=True)
    job_id = models.ForeignKey('swamplr_jobs.jobs')
    source_dir = models.CharField(max_length=255)
    replace_on_duplicate = models.CharField(max_length=1)
    subset = models.IntegerField(default=0)
    source_file_extension = models.CharField(max_length=10)
    contrast = models.IntegerField(default=0)
    brightness = models.IntegerField(default=0)

class job_derivatives(models.Model):

    job_derive_id = models.AutoField(primary_key=True)
    derive_id = models.ForeignKey('derivative_jobs')
    derive_type = models.CharField(max_length=32)
    parameters = models.CharField(max_length=1024)


class derivative_files(models.Model):
    """Table to relate filename to PID."""
    derive_file_id = models.AutoField(primary_key=True)
    job_derive_id = models.ForeignKey('job_derivatives')
    created = models.DateTimeField()
    source_file = models.CharField(max_length=255)
    target_file = models.CharField(max_length=255, null=True)
    result_id = models.ForeignKey('derivative_results')

class derivative_results(models.Model):

    result_id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=32)



