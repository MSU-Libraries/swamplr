from __future__ import unicode_literals

from django.apps import AppConfig
import os

class SwamplrIngestConfig(AppConfig):
    name = 'swamplr_ingest'
     

    # Build paths inside the project like this: os.path.join(BASE_DIR, ...)
    base_dir = os.path.dirname(__file__)

    # List of paths to make available in ingest directory browse.
    ingest_paths = ["/mnt/fedcom_ingest"]

    # Path to JSON file containing ingest type and collection configurations.
    collection_configs = os.path.join(base_dir, "collections.json")
    # Path to default configs.
    collection_defaults = os.path.join(base_dir, "collection_defaults.json")

