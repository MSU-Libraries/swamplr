# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-09-13 17:19
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_services', '0002_auto_20170906_1649'),
        ('swamplr_jobs', '0004_job_types_app_name'),
    ]

    operations = [
        migrations.RunSQL('UPDATE swamplr_jobs_job_types SET app_name = "swamplr_services" WHERE label="services";')
    ]