from .models import Budget
from django.utils import timezone
from datetime import datetime, date
from datetime import date, timedelta
from collections import defaultdict
from emailparser.models import StoredTransaction

def get_total_spending_current_month(user):
    today = date.today()
    current_year = today.year
    current_month = today.month

    total_spending = 0.0

    transactions = StoredTransaction.objects.filter(user=user)

    for txn in transactions:
        txn_data = txn.transaction_data
        if not isinstance(txn_data, dict): continue

        date_str = txn_data.get('date')
        if not date_str: continue

        from datetime import datetime
        parsed_date = None
        possible_formats = ["%d-%m-%y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"]
        for fmt in possible_formats:
            try:
                dt_obj = datetime.strptime(date_str.split()[0], fmt)
                parsed_date = dt_obj.date()
                break
            except ValueError: continue
        if parsed_date is None: continue

        if parsed_date.year == current_year and parsed_date.month == current_month:
            amount_val = txn_data.get('amount')
            if amount_val is None: continue
            try:
                amount = float(str(amount_val).replace(',', ''))
                if amount < 0: amount = abs(amount)
                total_spending += amount
            except (ValueError, TypeError): continue

    return total_spending

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
