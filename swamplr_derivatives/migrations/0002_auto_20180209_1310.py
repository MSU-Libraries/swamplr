# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-02-09 13:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_derivatives', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='derivative_jobs',
            name='brightness',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='derivative_jobs',
            name='contrast',
            field=models.IntegerField(default=0),
        ),
    ]