from django import forms
from django.forms import ModelForm
from django.core.urlresolvers import reverse
import views
from crispy_forms.helper import FormHelper
from django.utils.safestring import mark_safe
from crispy_forms.layout import Submit, Layout, Field, Fieldset, HTML
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.conf import settings


def validate_path(value):
    if not any([value.startswith(path) for path in settings.DATA_PATHS]):
        raise ValidationError(
            _('%(value)s is not an allowed path.'),
            params={'value': value},
        )

def get_slider_layout():
    """Return slider layout for contrast and brightness values."""
    layout = Layout(

        Fieldset(
            '',
            'path_list_selected',
            'derive_types',
            'replace_on_duplicate',
            'subset_value',
            HTML("""
              <input
                    type="text"
                    id="contrast-slider"
                    name="contrastslider"
                    data-provide="slider"
                    data-slider-min="-100"
                    data-slider-max="100"
                    data-slider-step="1"
                    data-slider-value="0"
                    data-slider-tooltip="show"
                >
            """),
            'contrast_value',
            HTML("""
              <input
                    type="text"
                    id="brightness-slider"
                    name="contrastslider"
                    data-provide="slider"
                    data-slider-min="-100"
                    data-slider-max="100"
                    data-slider-step="1"
                    data-slider-value="0"
                    data-slider-tooltip="show"
                >
            """),
            'brightness_value'
        )
    )


    return layout


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
        self.helper.layout = get_slider_layout()

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
        help_text = "{0} <p id='detail-option' data-toggle='popover' style='display:inline;' title='<strong>Command</strong>' data-content='{1}'><span class='label label-primary'>INFO</span></p>"
        help_data = {}
        for d in derive_options:
            dsettings = views.get_derive_settings(item_type.lower(), d)
            help_data[d] = {
                "label": dsettings["label"],
            }
            if "command" in dsettings:
                help_data[d]["command"] = dsettings["command"]
            else:
                option_key = "derive."+item_type.lower()+"."+d.lower()
                configs = views.get_configs()
                command_list = views.get_command_list(configs, item_type.lower(), option_key) 
                help_data[d]["command"] = "<br/>".join(["{0} {1}".format(c[0], c[1]) for c in command_list])

        self.fields["derive_types"] = forms.MultipleChoiceField(
            label = "Select derivatives types to create.",
            help_text = "",
            choices = [(d, mark_safe(help_text.format(help_data[d]["label"], help_data[d]["command"]))) for d in derive_options],
            widget=forms.CheckboxSelectMultiple()   
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
        self.fields["contrast_value"] = forms.CharField(label="Contrast", max_length="20",initial=0)
        self.fields["brightness_value"] = forms.CharField(label="Brightness", max_length="20", initial=0)


