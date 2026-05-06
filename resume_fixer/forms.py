from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import JobPosting, Resume, SavedJobSearch, UserProfile


FIELD_CLASS = 'form-control app-input'
SELECT_CLASS = 'form-select app-input'
CHECK_CLASS = 'form-check-input'


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Username',
        widget=forms.TextInput(attrs={
            'class': FIELD_CLASS,
            'placeholder': 'Enter your username',
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': FIELD_CLASS,
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        }),
    )


class AccountRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': FIELD_CLASS,
            'placeholder': 'you@example.com',
            'autocomplete': 'email',
        }),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': FIELD_CLASS,
                'placeholder': 'Choose a username',
                'autocomplete': 'username',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': FIELD_CLASS,
            'placeholder': 'Create a password',
            'autocomplete': 'new-password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': FIELD_CLASS,
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password',
        })


class ResumeUploadForm(forms.ModelForm):
    extracted_text = forms.CharField(
        required=False,
        label='Resume text',
        widget=forms.Textarea(attrs={
            'class': FIELD_CLASS,
            'rows': 10,
            'placeholder': 'Paste resume text here, or upload TXT, MD, CSV, DOCX, or a text-readable PDF.',
        }),
    )

    class Meta:
        model = Resume
        fields = ['title', 'file', 'extracted_text', 'is_primary']
        widgets = {
            'title': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Example: Software Engineer Resume'}),
            'file': forms.ClearableFileInput(attrs={'class': FIELD_CLASS}),
            'is_primary': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
        }


class JobPostingForm(forms.ModelForm):
    company_name = forms.CharField(
        max_length=200,
        label='Company',
        widget=forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Company name'}),
    )

    class Meta:
        model = JobPosting
        fields = [
            'company_name',
            'title',
            'location',
            'remote_type',
            'employment_type',
            'experience_level',
            'salary_min',
            'salary_max',
            'source_url',
            'description',
            'is_active',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Job title'}),
            'location': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Remote, city, state, etc.'}),
            'remote_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'employment_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'experience_level': forms.Select(attrs={'class': SELECT_CLASS}),
            'salary_min': forms.NumberInput(attrs={'class': FIELD_CLASS, 'placeholder': '90000'}),
            'salary_max': forms.NumberInput(attrs={'class': FIELD_CLASS, 'placeholder': '125000'}),
            'source_url': forms.URLInput(attrs={'class': FIELD_CLASS, 'placeholder': 'https://example.com/job'}),
            'description': forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 8, 'placeholder': 'Paste the job description here.'}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
        }


class SavedJobSearchForm(forms.ModelForm):
    class Meta:
        model = SavedJobSearch
        fields = ['name', 'query', 'location', 'min_salary', 'remote_only', 'is_alert_enabled']
        widgets = {
            'name': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Backend roles near Chicago'}),
            'query': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Python developer'}),
            'location': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Chicago, IL'}),
            'min_salary': forms.NumberInput(attrs={'class': FIELD_CLASS, 'placeholder': '80000'}),
            'remote_only': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
            'is_alert_enabled': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['user_type', 'target_role', 'target_location', 'remote_preference', 'minimum_salary']
        widgets = {
            'user_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'target_role': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Software Engineer'}),
            'target_location': forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'Remote or preferred city'}),
            'remote_preference': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
            'minimum_salary': forms.NumberInput(attrs={'class': FIELD_CLASS, 'placeholder': '80000'}),
        }
