# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-02-21 17:08
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_jobs', '0007_auto_20180219_1656'),
    ]

    operations = [
        migrations.RunSQL("""UPDATE swamplr_jobs_status SET status = "Complete" where status = "Success";"""),
        migrations.RunSQL("INSERT INTO swamplr_jobs_job_types (label, app_name) VALUES('delete', 'swamplr_ingest') ON DUPLICATE KEY UPDATE label=label;")
]
