from .models import Budget
from django.utils import timezone

def get_current_month_budget(user):
    """
    Returns the budget amount for the current month for the given user.
    """
    now = timezone.now()
    try:
        budget = Budget.objects.get(user=user, month=now.month, year=now.year).amount
    except Budget.DoesNotExist:
        budget = 0.0  
    return budget
