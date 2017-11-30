# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from models import namespace_cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render


def load_namespaces(request, count=25):
    """Load all namespaces from cache."""
    response = {
        "headings": ["#", "Namespace", "Count", "Actions"]
    }

    namespace_objects = namespace_cache.objects.all()
    paginator = Paginator(namespace_objects, count)
    page = request.GET.get('page')

    try:
        namespace_list = paginator.page(page)

    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        namespace_list = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        namespace_list = paginator.page(paginator.num_pages)

    for ns in namespace_list.object_list:

        set_namespace_info(ns)

    response["namespaces"] = namespace_list

    return render(request, 'swamplr_namespaces/namespaces.html', response)

def set_namespace_info(ns):
    """Prepare namespace object with additional info for display."""
    ns.actions = get_actions(ns)

def get_nav_bar():
    """Set contents of navigation bar for current app."""

    nav = {"label": "Namespaces",
           "name": "namespaces",
          }
    return nav

def get_actions(ns):
    """Required function: return actions to populate in job table."""
    list = {
         "method": "POST",
         "label": "List Items",
         "action": "list_items",
         "class": "btn-info",
         "args": ns.namespace
        }
    reindex = {
         "method": "POST",
         "label": "Reindex",
         "action": "reindex",
         "class": "btn-info",
         "args": ns.namespace
        }
    delete = {
         "method": "DELETE",
         "label": "Delete All",
         "action": "delete",
         "class": "btn-warning",
         "args": ns.namespace
        }
    return [list, reindex, delete]

