# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-12-13 16:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_namespaces', '0005_auto_20171204_2228'),
    ]

    operations = [
        migrations.CreateModel(
            name='object_ids',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pid', models.CharField(max_length=64, unique=True)),
                ('ark', models.CharField(max_length=64, null=True)),
                ('doi', models.CharField(max_length=64, null=True)),
                ('ark_minted', models.DateTimeField(null=True)),
                ('doi_minted', models.DateTimeField(null=True)),
            ],
        ),
        migrations.RunSQL("INSERT INTO swamplr_namespaces_namespace_operations (operation_name) VALUES('Mint DOI'), ('Mint ARK') ON DUPLICATE KEY UPDATE operation_name=operation_name;")
]
