from django import forms
from django.forms import ModelForm
from swamplr_services.models import services
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout


class ServicesForm(ModelForm):
 
    def __init__(self, *args, **kwargs):
        super(ServicesForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = "col-lg-4"
        self.helper.field_class = "col-lg-8"
        self.helper.form_method = 'post'
        self.helper.help_text_inline = True
        self.helper.form_action = 'add-service'
        self.helper.layout = Layout(
            "label",
            "description",
            "command",
            "run_as_user",
            Submit("add-service", "Add Service", css_class="btn-default"),
        )
        # self.helper.add_input(Submit('submit', 'Add Service'))

    run_as_user = forms.CharField(required=False)

    class Meta:
        model = services
        fields = ["label", "description", "command", "run_as_user"]

    
