# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login # Import the login function
from django.contrib.auth.decorators import login_required # To protect dashboard
from .forms import CustomSignUpForm # Import your custom form

from analytics.utils import (
    get_total_spending_current_month,
    get_num_spending_categories
)
from budgeting.utils import get_current_month_budget

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

def dashboard_view(request):
    total_spending = get_total_spending_current_month(request.user)
    
    context = {
        'total_spending': total_spending,
        # include other context as needed
    }

    return render(request, 'accounts/dashboard.html', context)

def dashboard_view(request):
    total_spending = get_total_spending_current_month(request.user)
    monthly_budget = get_current_month_budget(request.user)

    context = {
        'total_spending': total_spending,
        'monthly_budget': monthly_budget,
        # other context variables
    }

    return render(request, 'accounts/dashboard.html', context)

def dashboard_view(request):
    total_spending = get_total_spending_current_month(request.user)
    monthly_budget = get_current_month_budget(request.user)
    num_categories = get_num_spending_categories(request.user)

    context = {
        'total_spending': total_spending,
        'monthly_budget': monthly_budget,
        'num_categories': num_categories,
        # other context...
    }

    return render(request, 'accounts/dashboard.html', context)
