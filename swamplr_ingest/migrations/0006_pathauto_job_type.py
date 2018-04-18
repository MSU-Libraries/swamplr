# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_ingest', '0005_delete_objects_deleted'),
    ]

    operations = [
        migrations.RunSQL("INSERT INTO swamplr_jobs_job_types (label, app_name) VALUES('pathauto','swamplr_ingest') ON DUPLICATE KEY UPDATE label='pathauto', app_name='swamplr_ingest';")
]
