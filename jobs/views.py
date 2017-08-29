from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def jobs(request):
    pass

def main(request):
    """Landing page."""
    main = {}
    return render(request, 'jobs/main.html', main)

