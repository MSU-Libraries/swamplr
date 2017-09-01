# Custom context processors.

from swamplr_jobs.views import build_nav_bar
from swamplr_jobs.views import load_installed_apps


def load_swamplr(request):
    """Compute values to include in nav bar."""
    load_installed_apps()
    return {"nav_bar_options": build_nav_bar()}
