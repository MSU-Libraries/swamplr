# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-02-20 12:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_ingest', '0004_auto_20180219_1635'),
    ]

    operations = [
        migrations.AddField(
            model_name='delete_objects',
            name='deleted',
            field=models.DateTimeField(null=True),
        ),
    ]
