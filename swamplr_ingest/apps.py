from __future__ import unicode_literals

from django.apps import AppConfig
import os

class SwamplrIngestConfig(AppConfig):
    name = 'swamplr_ingest'
     

    # Build paths inside the project like this: os.path.join(BASE_DIR, ...)
    base_dir = os.path.dirname(__file__)

    # Path to JSON file containing ingest type and collection configurations.
    collection_configs = os.path.join(base_dir, "collections.json")
    # Path to default configs.
    collection_defaults = os.path.join(base_dir, "collection_defaults.json")

    # Path to fedora api configs. these will be typically stored at app-level as fedora_api/fedora/cfg.
    fedora_config_path = os.path.join(os.path.dirname(base_dir.rstrip('/')), "fedora_api", "fedora.cfg")
