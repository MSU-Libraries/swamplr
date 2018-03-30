from django import forms
from django.forms import ModelForm
from swamplr_services.models import services
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field


class ServicesForm(ModelForm):

    FREQUENCY_CHOICES = (
        ( 'MIN', 'Minutes'),
        ( 'HOUR', 'Hours'),
        ( 'DAY','Days'),
        ( 'WEEK', 'Weeks'),
    )
 
    def __init__(self, *args, **kwargs):
        super(ServicesForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-inline'
        self.helper.field_class = 'service-form'
        self.helper.form_method = 'post'
        self.helper.form_show_labels = False
        self.helper.help_text_inline = True
        self.helper.form_action = 'add-service'
        self.helper.layout = Layout(
            "label",
            "description",
            "command",
            "frequency",
            Field("frequency_time",css_class=" btn btn-info dropdown-toggle" ),
            "auto_archive",
            Field("auto_archive_time",css_class=" btn btn-info dropdown-toggle" ),
            "last_started",
            "run_as_user",
            Submit("add-service", "Add Service", css_class="btn btn-outline-success"),
        )

    run_as_user = forms.CharField(required=False, widget=forms.TextInput(
                                                      attrs={"placeholder": "User name",
                                                             "size": "15"}))
    label = forms.CharField(widget=forms.TextInput(
                                                      attrs={"placeholder": "Label"}))
    description = forms.CharField(widget=forms.TextInput(
                                                      attrs={"placeholder": "Description"}))
    command = forms.CharField(widget=forms.TextInput(
                                                      attrs={"placeholder": "Command",
                                                             "size": "41"}))
    frequency = forms.CharField(required=False, widget=forms.TextInput(
                                                      attrs={"placeholder": "Frequency",
                                                             "size": "10"}))
    frequency_time = forms.ChoiceField(required=False,  choices=FREQUENCY_CHOICES )
    
    auto_archive = forms.CharField(required=False, widget=forms.TextInput(
                                                      attrs={"placeholder": "Auto archive if success after...",
                                                             "size": "10"}))
    auto_archive_time = forms.ChoiceField(required=False,  choices=FREQUENCY_CHOICES )

    last_started = forms.CharField(required=False, widget=forms.HiddenInput())
  
    class Meta:
        model = services
        fields = ["label", "description", "command", "frequency", "auto_archive", "last_started", "run_as_user"]

    
