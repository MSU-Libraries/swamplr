from django import forms
from django.forms import ModelForm
from django.core.urlresolvers import reverse
from swamplr_ingest.models import ingest_jobs
import views
from apps import SwamplrIngestConfig
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

def validate_path(value):
    if not any([value.startswith(path) for path in settings.DATA_PATHS]): 
        raise ValidationError(
            _('%(value)s is not an allowed path.'),
            params={'value': value},
        )


class IngestForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(IngestForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.field_class = "col-lg-9"
        self.helper.label_class = "col-lg-3"
        self.helper.form_method = 'post'
        self.helper.form_show_labels = True
        self.helper.help_text_inline = True
        self.helper.add_input(Submit('submit', 'Ingest'))

    def set_form_action(self, collection_name):

        self.helper.form_action = reverse("add-ingest-job", args=[collection_name])

    def set_fields(self, collection_name):
        """Dynamically set fields on upload form depending on collection."""
        collection_data = views.get_ingest_data(collection_name)
    
        # Get any object type, and use it to retrieve namespace. 
        namespace_key = collection_data["objects"].keys()[0]
        namespace = collection_data["objects"][namespace_key]["namespace"]

        # Use first listed ingest path as default value.
        ingest_paths = settings.DATA_PATHS
        ingest_path = ingest_paths[0]

        self.fields["pid_namespace"] = forms.CharField(
            label="PID Namespace",
            required=True,
            initial=namespace, 
            max_length="20",
        )
        self.fields["path_list_selected"] = forms.CharField(
            required=True,
            label="Select directory",
            initial=ingest_path,
            validators=[validate_path],
        )
        for objectx, data in collection_data["objects"].items():
            # Determine if the object is required for ingest
            if data.get("required", "True") == "True": 
                obj_req = "obj-req"
            else:
                obj_req = ""

            # Gather datastream choices; these should be a tuple of 2-tuples containing label and ID.
            ds_choices = []
            for label, values in data["datastreams"].items():
                ds_choices.append((label, label))

            # Add choices to multiple choice field.
            ds_key = "{0}-{1}".format(objectx, "datastreams")
            ds_label = "{0}: {1}".format(data.get("label", objectx), "datastreams")
            self.fields[ds_key] = forms.MultipleChoiceField(
                label=ds_label,
                choices=tuple(ds_choices),
                required=False,
                help_text="",
                widget=forms.CheckboxSelectMultiple(attrs={"checked": "checked", "class": obj_req}))

            # Gather metadata choices.
            meta_choices = []
            for label, values in data["metadata"].items():
                meta_choices.append((label, label))

            # Form field for metadata.
            meta_key = "{0}-{1}".format(objectx, "metadata")
            meta_label = "{0}: {1}".format(data.get("label", objectx), "metadata")
            self.fields[meta_key] = forms.MultipleChoiceField(
                label=meta_label,
                required=False,
                choices=tuple(meta_choices),
                help_text="",
                widget=forms.CheckboxSelectMultiple(attrs={"checked": "checked", "class": obj_req}))

        self.fields["process"] = forms.MultipleChoiceField(
            required=False,
            label="Process existing objects and/or create new objects.",
            help_text="",
            choices=(
                ("process_new", "Create new objects."),
                ("process_existing", "Add new datastreams to existing objects."),
            ),
            widget=forms.CheckboxSelectMultiple(attrs={"checked": "checked"})   
        )

        self.fields["replace_on_duplicate"] = forms.BooleanField(
            required=False,
            label="Replace existing metadata and datastreams.",
            help_text="Leave unchecked to only add new datastreams (not replace existing ones). This option only applies when updating existing objects.")

        self.fields["subset_value"] = forms.IntegerField(
            required=False,
            label="Subset",
            min_value=0,
            help_text="Optionally select a number of items to process. Leave blank to process all items."
        )

