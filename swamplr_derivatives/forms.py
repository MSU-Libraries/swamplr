from django import forms
from django.forms import ModelForm
from django.core.urlresolvers import reverse
import views
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

class DerivativesForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(DerivativesForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.field_class = "col-lg-9"
        self.helper.label_class = "col-lg-3"
        self.helper.form_method = 'post'
        self.helper.form_show_labels = True
        self.helper.help_text_inline = True
        self.helper.add_input(Submit('submit', 'Start'))

    def set_form_action(self, item_type):

        self.helper.form_action = reverse("add-derivatives-job", args=[item_type])

    def set_fields(self, item_type):
        """Dynamically set fields on upload form depending on collection."""
        derive_options = views.get_derive_data(item_type)

        # Use first listed path as default value.
        default_paths = settings.DATA_PATHS
        default_path = default_paths[0]

        self.fields["path_list_selected"] = forms.CharField(
            required=True,
            label="Select directory",
            initial=default_path,
            validators=[validate_path],
        )
        self.fields["derive_types"] = forms.MultipleChoiceField(
            label = "Select derivatives types to create.",
            help_text = "",
            choices = [(d, d) for d in derive_options],
            widget=forms.CheckboxSelectMultiple(attrs={"checked": "checked"})   

        )

        self.fields["replace_on_duplicate"] = forms.BooleanField(
            required=False,
            label="Replace existing derivative files.",
            help_text="",
        )

        self.fields["subset_value"] = forms.IntegerField(
            required=False,
            label="Subset",
            min_value=0,
            help_text="Optionally select a number of items to process. Leave blank to process all items."
        )


