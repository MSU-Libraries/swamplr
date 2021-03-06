# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-09-27 17:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('swamplr_jobs', '0006_auto_20170927_1709'),
    ]

    operations = [
        migrations.CreateModel(
            name='datastreams',
            fields=[
                ('datastream_id', models.AutoField(primary_key=True, serialize=False)),
                ('datastream_label', models.CharField(max_length=16)),
                ('is_object', models.CharField(max_length=1)),
            ],
        ),
        migrations.CreateModel(
            name='ingest_jobs',
            fields=[
                ('ingest_id', models.AutoField(primary_key=True, serialize=False)),
                ('source_dir', models.CharField(max_length=255)),
                ('collection_name', models.CharField(max_length=255)),
                ('namespace', models.CharField(max_length=255)),
                ('replace_on_duplicate', models.CharField(max_length=1)),
                ('process_new', models.CharField(max_length=1)),
                ('process_existing', models.CharField(max_length=1)),
                ('subset', models.IntegerField(default=0)),
                ('rels_ext_from_file', models.CharField(max_length=1)),
                ('rels_ext_generated', models.CharField(max_length=1)),
                ('job_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='swamplr_jobs.jobs')),
            ],
        ),
        migrations.CreateModel(
            name='job_datastreams',
            fields=[
                ('job_datastream_id', models.AutoField(primary_key=True, serialize=False)),
                ('datastream_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='swamplr_ingest.datastreams')),
                ('ingest_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='swamplr_ingest.ingest_jobs')),
            ],
        ),
        migrations.CreateModel(
            name='job_objects',
            fields=[
                ('object_id', models.AutoField(primary_key=True, serialize=False)),
                ('created', models.DateTimeField()),
                ('obj_file', models.CharField(max_length=255, null=True)),
                ('pid', models.CharField(max_length=64, null=True)),
                ('job_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='swamplr_jobs.jobs')),
            ],
        ),
        migrations.CreateModel(
            name='object_results',
            fields=[
                ('result_id', models.AutoField(primary_key=True, serialize=False)),
                ('label', models.CharField(max_length=32)),
            ],
        ),
        migrations.AddField(
            model_name='job_objects',
            name='result_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='swamplr_ingest.object_results'),
        ),
        migrations.RunSQL("INSERT INTO swamplr_jobs_job_types (label, app_name) VALUES('ingest', 'swamplr_ingest') ON DUPLICATE KEY UPDATE label=label;"),
        migrations.RunSQL("INSERT INTO swamplr_ingest_object_results (label) VALUES('Success'), ('Failure'), ('Skipped') ON DUPLICATE KEY UPDATE label=label;"),
        
    ]
