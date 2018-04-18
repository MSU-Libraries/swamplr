# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('swamplr_namespaces', '0006_object_ids'),
    ]

    operations = [
        migrations.RunSQL("INSERT INTO swamplr_namespaces_namespace_operations (operation_name) VALUES('Pathauto') ON DUPLICATE KEY UPDATE operation_name=operation_name;")
]
