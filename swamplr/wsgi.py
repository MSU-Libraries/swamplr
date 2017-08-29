"""
WSGI config for swamplr project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "swamplr.settings")
# TODO: Fix so we no longer need this hack.
# Because WSGIPythonPath is not being included, we have temporarily added this
# hack to force the application path into the system path
import sys
path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if path not in sys.path:
    sys.path.append(path)

application = get_wsgi_application()
