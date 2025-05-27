from django import forms
from .models import Project, ProjectImage
from authentication.models import CoworkingUser

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'working_field', 'github_link']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class ProjectImageForm(forms.ModelForm):
    class Meta:
        model = ProjectImage
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'multiple': False}),
        }

class TeamMemberForm(forms.Form):
    team_members = forms.ModelMultipleChoiceField(
        queryset=CoworkingUser.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )