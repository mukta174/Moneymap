# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login # Import the login function
from django.contrib.auth.decorators import login_required # To protect dashboard
from .forms import CustomSignUpForm # Import your custom form

def home_page_view(request):
    """ Displays the public landing page. """
    context = {}
    return render(request, 'accounts/home.html', context)

def sign_up_view(request):
    """ Handles user registration. """
    if request.method == 'POST':
        form = CustomSignUpForm(request.POST)
        if form.is_valid():
            user = form.save() # Save User and Profile
            login(request, user) # Log the user in directly after signup
            return redirect('dashboard') # Redirect to the dashboard page
        # If form is invalid, it will be re-rendered with errors below
    else: # GET request
        form = CustomSignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})

@login_required # This decorator ensures only logged-in users can access this view
def dashboard_view(request):
    """ Displays the main dashboard page after login. """
    # You can fetch user-specific data here later
    context = {
        'user': request.user
    }
    return render(request, 'accounts/dashboard.html', context)

# Note: Login and Logout views are handled by django.contrib.auth.urls