# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-09-23 14:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_jobs', '0004_job_types_app_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobs',
            name='archived',
            field=models.CharField(blank=True, max_length=1),
        ),
    ]