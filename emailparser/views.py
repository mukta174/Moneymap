# email_parser/views.py
import os
import joblib
import nltk # type: ignore
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required 
from django.contrib import messages 
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from .email_utils import get_transactions 
from .forms import AppPasswordForm
from .models import StoredTransaction 
import nltk

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

#Model Loading
MODEL_PATH = os.path.join(settings.BASE_DIR, 'expense_classifier.pkl')
MODEL = None
MODEL_LOAD_ERROR = None

print(f"DEBUG: Attempting to load model from: {MODEL_PATH}")
try:
    if os.path.exists(MODEL_PATH):
        MODEL = joblib.load(MODEL_PATH)
        print("DEBUG: Expense classification model loaded successfully.")
    else:
        MODEL_LOAD_ERROR = f"Model file not found at '{MODEL_PATH}'. Auto-categorization disabled."
        print(f"ERROR: {MODEL_LOAD_ERROR}")
except Exception as e:
    MODEL_LOAD_ERROR = f"Error loading model '{MODEL_PATH}': {e}. Auto-categorization disabled."
    print(f"ERROR: {MODEL_LOAD_ERROR}")
    MODEL = None


def categorize_transactions(transactions):
    """
    Helper function to categorize transactions using the loaded model
    """
    if not MODEL:
        # If model isn't available, mark all as N/A
        for txn in transactions:
            txn['category'] = 'N/A (Model Error)'
        return transactions, []
    
    errors = []
    for txn in transactions:
        try:
            description = txn.get('party_name', '')
            if description:
                predicted_category = MODEL.predict([description])[0]
                txn['category'] = predicted_category
                print(f"  DEBUG: Categorized '{description}' as '{predicted_category}'")
            else:
                txn['category'] = 'Unknown Description'
                print("  DEBUG: Skipping categorization for transaction with empty description.")
        except Exception as e:
            txn['category'] = 'Categorization Error'
            error_msg = f"Error categorizing '{description or 'N/A'}': {e}"
            print(f"ERROR: {error_msg}")
            errors.append(error_msg)
    
    return transactions, errors


def save_transactions_to_db(user, transactions):
    """
    Save fetched transactions to database for this user
    """
    saved_count = 0
    for txn in transactions:
        # Use transaction_id or create a unique identifier to avoid duplicates
        transaction_id = txn.get('transaction_id', None)
        if not transaction_id:
            # If no transaction_id is available, create one from date and amount
            date_str = txn.get('date', str(datetime.now()))
            amount = txn.get('amount', '0.00')
            description = txn.get('party_name', 'unknown')
            transaction_id = f"{date_str}_{amount}_{description}"
        
        # Check if this transaction is already stored
        if not StoredTransaction.objects.filter(
            user=user,
            transaction_id=transaction_id
        ).exists():
            # Store new transaction
            StoredTransaction.objects.create(
                user=user,
                transaction_id=transaction_id,
                transaction_data=txn,
                fetched_date=timezone.now()
            )
            saved_count += 1
    
    return saved_count


# emailparser/views.py
# Previous imports remain the same...

@login_required 
def fetch_and_categorize_expenses(request):
    """
    Handles requesting app password (GET) and fetching/categorizing expenses (POST).
    Uses the logged-in user's email address and bank preference.
    """
    user_email = request.user.email
    
    # Get user's bank preference from profile
    try:
        user_bank = request.user.profile.bank_to_track
        print(f"DEBUG: User bank from profile: {user_bank}")
    except Exception as e:
        user_bank = None
        print(f"DEBUG: Error retrieving user bank from profile: {e}")
    
    # Set context with bank info
    context = {
        'transactions': None,
        'errors': [],
        'model_error': MODEL_LOAD_ERROR, 
        'form': None, #AppPasswordForm instance
        'user_email': user_email,
        'user_bank': user_bank,  # Add bank info to context
        'show_results': True,  # Always show results if there are stored transactions
        'last_fetch': None
    }

    # Validate user has email and bank selection
    if not user_email:
        messages.error(request, "Your account profile needs an email address to fetch transactions.")
        return redirect('home') # Redirect home for now
    
    if not user_bank:
        messages.error(request, "Unable to determine which bank to track. Please update your profile.")
        context['errors'].append("No bank selected in user profile. Please update your profile settings.")
        print("DEBUG: No bank selection found in user profile")
    
    # Get stored transactions for this user
    stored_transactions = StoredTransaction.objects.filter(user=request.user).order_by('-transaction_data__date')
    
    if stored_transactions.exists():
        # Get the latest fetch date
        latest_transaction = stored_transactions.order_by('-fetched_date').first()
        context['last_fetch'] = latest_transaction.fetched_date
        
        # Extract transaction data from stored transactions
        context['transactions'] = [txn.transaction_data for txn in stored_transactions]
        messages.info(request, f"Displaying {len(stored_transactions)} stored transactions. Last updated: {context['last_fetch']}")

    # Handle fetch request
    if request.method == 'POST' and 'fetch_new' in request.POST:
        form = AppPasswordForm(request.POST)
        context['form'] = form
        
        if form.is_valid():
            app_password = form.cleaned_data['app_password']
            
            # Check if we have a valid bank selection
            if not user_bank:
                messages.error(request, "Unable to determine which bank to track. Please update your profile.")
                # Still continue with form to allow user to make another attempt
            else:
                # Fetching logic with bank parameter
                messages.info(request, f"Fetching new transactions for {user_email} ({user_bank} Bank)... This may take a moment.")
                print(f"DEBUG: Fetching transactions for {user_email} via trigger view for {user_bank} Bank...")
                
                try:
                    # Pass the bank parameter to get_transactions
                    result = get_transactions(user_email, app_password, user_bank)
                    fetched_transactions = result.get('transactions', [])
                    fetch_errors = result.get('errors', [])
                    context['errors'].extend(fetch_errors)
                    
                    if fetched_transactions:
                        # Auto-categorize the transactions
                        categorized_transactions, categorization_errors = categorize_transactions(fetched_transactions)
                        context['errors'].extend(categorization_errors)
                        
                        # Save transactions to database
                        new_count = save_transactions_to_db(request.user, categorized_transactions)
                        
                        if new_count > 0:
                            messages.success(request, f"Added {new_count} new transactions from {user_bank} Bank to your stored data.")
                            
                            # Refresh the transaction list with all stored transactions
                            stored_transactions = StoredTransaction.objects.filter(user=request.user).order_by('-transaction_data__date')
                            context['transactions'] = [txn.transaction_data for txn in stored_transactions]
                            context['last_fetch'] = timezone.now()
                        else:
                            messages.info(request, f"No new transactions found for {user_bank} Bank.")
                    
                    elif not fetched_transactions and not fetch_errors:
                        messages.info(request, f"No new transactions found for {user_bank} Bank.")
                    
                    if fetch_errors:
                        messages.error(request, "There were errors fetching transactions. See details below.")
                
                except Exception as e:
                    error_msg = f"An unexpected error occurred: {e}"
                    print(f"ERROR: {error_msg}")
                    messages.error(request, error_msg)
                    context['errors'].append(error_msg)
        
        else:
            # Form is invalid
            messages.error(request, "Please enter your App Password.")
    
    # For GET requests or when showing stored data
    elif request.method == 'GET':
        form = AppPasswordForm()
        context['form'] = form
    
    # Determine which template to use
    if context['transactions'] or ('show_results' in context and context['show_results']):
        template_name = 'emailparser/display_fetched_expenses.html'
    else:
        template_name = 'emailparser/request_app_password.html'
    
    return render(request, template_name, context)