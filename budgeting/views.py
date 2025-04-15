from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models import Budget, Expense
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum
from .utils import get_current_month_budget
from analytics.utils import get_total_spending_current_month
from decimal import Decimal


@login_required
def budget_page(request):
    """
    View to display the budget page with current budget status
    """
    # Get the current month and year
    current_date = timezone.now()
    current_month = current_date.month
    current_year = current_date.year
    
    # Get user's current budget for this month
    try:
        budget_obj = Budget.objects.get(
            user=request.user,
            month=current_month,
            year=current_year
        )
        budget = budget_obj.amount
    except Budget.DoesNotExist:
        budget = None
    
    # Calculate spent amount and remaining budget
    if budget:
        # Get total expenses for current month
        spent = Decimal(str(get_total_spending_current_month(request.user)))
        
        remaining = budget - spent
        
        # Calculate progress percentage for the progress bar
        progress_percentage = min((remaining / budget) * 100, 100) if budget > 0 else 0
    else:
        spent = 0
        remaining = 0
        progress_percentage = 0
    
    context = {
        'budget': budget,
        'spent': spent,
        'remaining': remaining,
        'abs_remaining': abs(remaining),
        'progress_percentage': progress_percentage,
    }
    
    return render(request, 'budgeting/budget.html', context)

@login_required
@require_http_methods(["POST"])
def update_budget(request):
    """
    View to handle budget update from the modal form
    """
    try:
        budget_amount = float(request.POST.get('budget', 0))
        if budget_amount <= 0:
            return JsonResponse({'error': 'Budget must be greater than zero'}, status=400)
        
        current_date = timezone.now()
        current_month = current_date.month
        current_year = current_date.year
        
        # Update or create budget for current month
        budget_obj, created = Budget.objects.update_or_create(
            user=request.user,
            month=current_month,
            year=current_year,
            defaults={'amount': budget_amount}
        )
        
        return redirect('budget_page')
        
    except ValueError:
        return JsonResponse({'error': 'Invalid budget amount'}, status=400)
    
def budget_view(request):
    # Get the current month's budget and total spending using existing utilities
    budget = get_current_month_budget(request.user)
    spent = get_total_spending_current_month(request.user)
    
    # Safely calculate remaining
    remaining = (budget or 0) - (spent or 0)

    context = {
        'budget': budget,
        'spent': spent,
        'remaining': remaining,
    }
    
    return render(request, 'budget.html', context)