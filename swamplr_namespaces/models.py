# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


class namespace_operations(models.Model):

    operation_id = models.AutoField(primary_key=True)
    operation_name = models.CharField(max_length=32)
    
class namespace_jobs(models.Model):

    job_id = models.OneToOneField("swamplr_jobs.jobs", primary_key=True, on_delete=models.CASCADE) 
    operation_id = models.ForeignKey("namespace_operations")
    namespace = models.CharField(max_length=64)

class namespace_cache(models.Model):

    namespace = models.CharField(max_length=64, unique=True)
    count = models.IntegerField(default=0)

class cache_job(models.Model):

    process_id = models.IntegerField(null=True)
    last_run = models.DateTimeField(null=True)
    
