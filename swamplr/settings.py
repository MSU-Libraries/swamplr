"""
Django settings for swamplr project.

Generated by 'django-admin startproject' using Django 1.10.5.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import os
from ConfigParser import ConfigParser
import logging

def load_configs(path_to_configs):
    """Load configs from default location."""
    configs = ConfigParser()
    # Load configs preserving case
    configs.optionxform = str
    # Individual configs accessed via configs object.
    configs.readfp(open(path_to_configs))
    return configs

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Not auto-appending slash to url as that results in loss of data in redirect to url with slash.
APPEND_SLASH = False

# Secure settings (including passwords) stored in additional settings file, and loaded below.
SECURE_SETTINGS = os.path.join(BASE_DIR, "swamplr.cfg")

# Load configs from location in SECURE_SETTINGS
configs = load_configs(SECURE_SETTINGS)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = configs.get("secretkey", "SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
# If value is 'true' set python boolean object to True, else False.
DEBUG = configs.get("debug", "DEBUG").lower() == 'true'

if DEBUG:
    # will output to console
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%a, %d %b %Y %H:%M:%S', filemode='w')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%a, %d %b %Y %H:%M:%S', filemode='w')

# This is the list of valid hostnames that Django is allowed to
# respond to. e.g. swamplr.example.edu, etc
ALLOWED_HOSTS = [host.strip() for host in configs.get("hosts", "ALLOWED_HOSTS").split(",")]

# Fedora connection information.
FEDORA_URL = configs.get("fedora", "FEDORA_URL")
FEDORA_USER = configs.get("fedora", "FEDORA_USER")
FEDORA_PASSWORD = configs.get("fedora", "FEDORA_PASSWORD")

# Gsearch server info and credentials
GSEARCH_USER = configs.get("gsearch", "GSEARCH_USER")
GSEARCH_PASSWORD = configs.get("gsearch", "GSEARCH_PASSWORD")
GSEARCH_URL = configs.get("gsearch", "GSEARCH_URL")

# EZID credentials
EZID_USER = configs.get("ezid", "EZID_USER")
EZID_PASSWORD = configs.get("ezid", "EZID_PASSWORD")
DOI_SHOULDER = configs.get("ezid", "DOI_SHOULDER")
ARK_SHOULDER = configs.get("ezid", "ARK_SHOULDER")

# Application definition
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'swamplr_jobs',
    'swamplr_services',
    'swamplr_ingest',
    'swamplr_namespaces',
)

CRISPY_TEMPLATE_PACK = 'bootstrap3'

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'swamplr.urls'

WSGI_APPLICATION = 'swamplr.wsgi.application'

# Database
DATABASES = {'default': dict(configs.items("database.default"))}
# Check for ATOMIC_REQUESTS setting. If not set, defaults to True.
ATOMIC_REQUESTS = DATABASES['default'].get('ATOMIC_REQUESTS', "True").lower() == "true"
DATABASES['default']['ATOMIC_REQUESTS'] = ATOMIC_REQUESTS

# Activating STRICT_ALL_TABLES mode forces truncated strings inserted into
# the database to produce errors instead of warnings.
DATABASES['default']['OPTIONS'] = {'sql_mode': 'STRICT_ALL_TABLES'}

# Internationalization
TIME_ZONE = "America/Detroit"

LANGUAGE_CODE = 'en-us'

USE_I18N = True

USE_L10N = True

USE_TZ = False

# Template information
TEMPLATES = [
    {'BACKEND': 'django.template.backends.django.DjangoTemplates',
     'DIRS': [],
     'APP_DIRS': True,
     'OPTIONS': {'context_processors': [
         # Insert your TEMPLATE_CONTEXT_PROCESSORS here or use this
         # list if you haven't customized them:
         'django.contrib.auth.context_processors.auth',
         'django.template.context_processors.debug',
         'django.template.context_processors.i18n',
         'django.template.context_processors.media',
         'django.template.context_processors.static',
         'django.template.context_processors.tz',
         'django.contrib.messages.context_processors.messages',
         'swamplr_jobs.context_processors.load_swamplr',
         ],
         'debug': configs.get("debug", "DEBUG").lower() == 'true'},
     },
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = '/var/www/swamplr/static'

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



