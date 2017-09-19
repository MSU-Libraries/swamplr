# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-09-06 16:49
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('swamplr_jobs', '0002_auto_20170906_1649'),
        ('swamplr_services', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='service_jobs',
            fields=[
                ('job_id', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='swamplr_jobs.jobs')),
            ],
        ),
        migrations.CreateModel(
            name='services',
            fields=[
                ('service_id', models.AutoField(primary_key=True, serialize=False)),
                ('label', models.CharField(max_length=32)),
                ('description', models.CharField(max_length=1024, null=True)),
                ('command', models.CharField(max_length=1024)),
                ('run_as_user', models.CharField(max_length=16, null=True)),
            ],
        ),
        migrations.AddField(
            model_name='service_jobs',
            name='service_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='swamplr_services.services'),
        ),
    ]