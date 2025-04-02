# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Profile, BANK_CHOICES # Import Profile and choices

User = get_user_model()

class CustomSignUpForm(UserCreationForm):
    # Add fields from the standard User model that we want on the signup form
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    # Add custom fields from the Profile model
    occupation = forms.CharField(max_length=100, required=False) # Make it optional here if desired
    bank_to_track = forms.ChoiceField(choices=BANK_CHOICES, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        # Include standard fields + our added User fields
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email',)

    def save(self, commit=True):
        # Save the User instance first
        user = super().save(commit=False) # Don't commit yet

        # Set username same as email by default (ensure email is unique in User model if doing this)
        # Note: Django's default User model requires username.
        # If you want *only* email login later, you'd need a custom User model.
        user.username = self.cleaned_data['email']

        if commit:
            user.save() # Save the User

            # Now save the Profile data
            profile = user.profile # Access the related profile (created by signal or get_or_create)
            profile.occupation = self.cleaned_data.get('occupation')
            profile.bank_to_track = self.cleaned_data.get('bank_to_track')
            profile.save()

        return user

# Optional: Customize Login Form appearance if needed, but uses standard fields
# For now, we'll use the default AuthenticationForm and style the template
# If you strictly need an EMAIL field instead of USERNAME on login form:
# class EmailAuthenticationForm(AuthenticationForm):
#     username = forms.EmailField(widget=forms.EmailInput(attrs={'autofocus': True}))