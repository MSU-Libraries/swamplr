# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-09-27 17:09
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_jobs', '0005_jobs_archived'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='job_objects',
            name='job_id',
        ),
        migrations.DeleteModel(
            name='job_objects',
        ),
    ]
