from django.shortcuts import render

# Create your views here.

def reload_solr():
    pass

def reset_djatoka():
    pass

def get_nav_bar():
    
    nav =  {"label": "Services",
            "name": "services",
   	    "children": [
                         {"label": "Reload Solr",
       		          "url": "reload_solr",
                          "name": "reload_solr"},
                         {"label": "Reset Djatoka",
                          "url": "reset_djatoka",
                          "name": "reset_djatoka"},
                        ]
           }
    return nav
