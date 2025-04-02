# email_parser/forms.py

from django import forms

class AppPasswordForm(forms.Form):
    """A simple form to collect the user's email app password."""
    app_password = forms.CharField(
        label="Email App Password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), # Prevent browser saving if desired
        required=True,
        help_text="Enter the App Password generated from your email provider (e.g., Gmail, Outlook) for Moneymap."
    )