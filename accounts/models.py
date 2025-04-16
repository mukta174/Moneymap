# accounts/models.py
from django.db import models
from django.conf import settings # To get the User model
# Move signal imports down if they were higher
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.contrib.auth import get_user_model
from django.contrib.auth.models import User

# Define choices for the bank dropdown
BANK_CHOICES = [
    ('HDFC', 'HDFC Bank'),
    ('ICICI', 'ICICI Bank'),
    ('SBI', 'State Bank of India'),
    ('AXIS', 'Axis Bank'),
    ('KOTAK', 'Kotak Mahindra Bank'),
    ('OTHER', 'Other/Not Listed'),
    # Add more banks as needed
]

# --- DEFINE THE PROFILE CLASS FIRST ---
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile') # Added related_name
    occupation = models.CharField(max_length=100, blank=True, null=True)
    bank_to_track = models.CharField(
        max_length=50,
        choices=BANK_CHOICES,
        default='HDFC',
        blank=False,
        null=False
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"

# --- NOW DEFINE THE SIGNAL RECEIVER ---
# Import signal-related things here, AFTER Profile is defined
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model() # Get the active User model

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        # Use get_or_create for robustness, though signal should only fire once on create
        Profile.objects.get_or_create(user=instance)
    # Ensure profile exists before trying to save (important if signal runs before profile creation somehow)
    # The get_or_create above handles the creation part.
    # Saving the profile might be redundant if no profile fields are updated when the User is saved,
    # unless you add logic to update profile based on user changes.
    # Let's simplify: only create on user creation. Updates can happen elsewhere if needed.
    # instance.profile.save() # Remove this line for now unless needed later