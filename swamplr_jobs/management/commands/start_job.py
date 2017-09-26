from django.core.management.base import BaseCommand, CommandError
from swamplr_jobs import views
from swamplr_jobs.models import jobs, status
import logging

class Command(BaseCommand):
    help = 'Starts a new job from the DB'

    def handle(self, *args, **options):
	# Perform any necessary pre-processing required by the installed apps
	views.pre_process()

        job_queued_status_id = status.objects.get(default="y")
        incomplete_job = jobs.objects.filter(status_id_id=job_queued_status_id).first()
        if not incomplete_job:

            return None

        else:
            views.process_job(incomplete_job)

