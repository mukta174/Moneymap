# accounts/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator
from .models import Profile, BANK_CHOICES # Import Profile and choices

User = get_user_model()

class EditProfileForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'input-field', 'autocomplete': 'off'})
    )
    email = forms.EmailField(
        validators=[EmailValidator()],
        widget=forms.EmailInput(attrs={'class': 'input-field'})
    )
    bank_name = forms.ChoiceField(
        choices=BANK_CHOICES,
        widget=forms.Select(attrs={'class': 'input-field'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if User.objects.filter(username__iexact=username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Username already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Email already in use.")
        return email

class CustomSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    # Add custom fields from the Profile model
    occupation = forms.CharField(max_length=100, required=False) # Make it optional here if desired
    
    # Use bank_to_track instead of bank - fix this key issue
    bank_to_track = forms.ChoiceField(choices=BANK_CHOICES, required=True, 
                              label="Bank to Track",
                              help_text="Select the bank whose transactions you want to track")

    class Meta(UserCreationForm.Meta):
        model = User
        # Include standard fields + our added User fields
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email',)

    def save(self, commit=True):
        # Save the User instance first
        user = super().save(commit=False) # Don't commit yet

        # Set username same as email by default
        user.username = self.cleaned_data['email']

        if commit:
            user.save() # Save the User

            # Now save the Profile data
            profile = user.profile # Access the related profile (created by signal or get_or_create)
            profile.occupation = self.cleaned_data.get('occupation')
            profile.bank_to_track = self.cleaned_data.get('bank_to_track')  # Make sure this key matches
            profile.save()

        return user