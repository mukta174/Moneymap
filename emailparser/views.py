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
# Removed duplicate datetime import

try:
    nltk.data.find('corpora/stopwords')
    print("DEBUG: NLTK stopwords found.")
except nltk.downloader.DownloadError:
    print("DEBUG: NLTK stopwords not found, attempting download...")
    try:
        nltk.download('stopwords')
        print("DEBUG: NLTK stopwords downloaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to download NLTK stopwords: {e}")

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
    if not MODEL:
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
    saved_count = 0
    for txn in transactions:
        transaction_id = txn.get('transaction_id', None)
        if not transaction_id:
            date_str = txn.get('date', str(datetime.now().strftime("%Y-%m-%d"))) # Ensure consistent date format for ID
            amount = txn.get('amount', '0.00')
            description = txn.get('party_name', 'unknown')
            transaction_id = f"{date_str}_{amount}_{description}"

        if not StoredTransaction.objects.filter(
            user=user,
            transaction_id=transaction_id
        ).exists():
            StoredTransaction.objects.create(
                user=user,
                transaction_id=transaction_id,
                transaction_data=txn,
                fetched_date=timezone.now()
            )
            saved_count += 1
    return saved_count


# Helper function to parse date from transaction_data for sorting
def _parse_transaction_date(txn_object):
    """
    Parses the date from a StoredTransaction object's transaction_data.
    Returns a datetime object for sorting, or datetime.min if parsing fails.
    """
    date_str = txn_object.transaction_data.get('date', '')
    # Order of formats can matter if a date string could ambiguously match multiple.
    # E.g., "01-02-2023" could be Jan 2 or Feb 1 depending on %d-%m or %m-%d.
    # Assuming get_transactions standardizes date output or we handle common variations.
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    print(f"DEBUG: Could not parse date string: '{date_str}' for StoredTransaction ID: {txn_object.id}, transaction_id: {txn_object.transaction_id}")
    return datetime.min # Treat unparseable dates as very old (appear at the bottom when reverse=True)

@login_required
def fetch_and_categorize_expenses(request):
    user_email = request.user.email

    try:
        user_bank = request.user.profile.bank_to_track
        print(f"DEBUG: User bank from profile: {user_bank}")
    except AttributeError: # Catches if 'profile' or 'bank_to_track' doesn't exist
        user_bank = None
        print("DEBUG: User profile or bank_to_track attribute not found.")
    except Exception as e: # General catch-all for other Profile-related errors
        user_bank = None
        print(f"DEBUG: Error retrieving user bank from profile: {e}")

    context = {
        'transactions': [], # Initialize with an empty list
        'errors': [],
        'model_error': MODEL_LOAD_ERROR,
        'form': AppPasswordForm(), # Initialize form for GET request
        'user_email': user_email,
        'user_bank': user_bank,
        'show_results': True,
        'last_fetch': None
    }

    if not user_email:
        messages.error(request, "Your account profile needs an email address to fetch transactions.")
        return redirect('home') # Consider redirecting to a profile update page

    if not user_bank:
        # This message is for display, fetching will be disabled later if bank is still None
        messages.warning(request, "Bank to track is not set in your profile. Please update your profile to fetch new transactions.")
        context['errors'].append("No bank selected in user profile. Please update your profile settings.")
        print("DEBUG: No bank selection found in user profile for fetching.")

    # Load and sort existing stored transactions for initial display
    stored_transaction_objects = list(StoredTransaction.objects.filter(user=request.user))

    if stored_transaction_objects:
        # Sort StoredTransaction objects by the 'date' in their transaction_data, newest first
        stored_transaction_objects.sort(key=_parse_transaction_date, reverse=True)
        
        context['transactions'] = [txn.transaction_data for txn in stored_transaction_objects]
        
        try:
            latest_fetch_object = max(stored_transaction_objects, key=lambda txn: txn.fetched_date)
            context['last_fetch'] = latest_fetch_object.fetched_date
            messages.info(request, f"Displaying {len(stored_transaction_objects)} stored transactions, sorted by date (newest first). Last updated: {context['last_fetch']}")
        except ValueError: # Should not happen if stored_transaction_objects is not empty
             print("DEBUG: Error finding max fetched_date, though transactions exist.")
    else:
        # No stored transactions, context['transactions'] remains an empty list
        messages.info(request, "No stored transactions found. Try fetching new ones.")


    if request.method == 'POST' and 'fetch_new' in request.POST:
        form = AppPasswordForm(request.POST)
        context['form'] = form # Update context with the POSTed form

        if form.is_valid():
            app_password = form.cleaned_data['app_password']

            if not user_bank: # Crucial check before attempting to fetch
                messages.error(request, "Cannot fetch transactions: Bank to track is not set in your profile.")
            else:
                messages.info(request, f"Fetching new transactions for {user_email} ({user_bank} Bank)... This may take a moment.")
                print(f"DEBUG: Fetching transactions for {user_email} via trigger view for {user_bank} Bank...")

                try:
                    result = get_transactions(user_email, app_password, user_bank)
                    fetched_transactions_list = result.get('transactions', [])
                    fetch_errors = result.get('errors', [])
                    context['errors'].extend(fetch_errors) # Add errors from get_transactions

                    current_fetch_time = timezone.now() # Record time of this fetch attempt

                    if fetched_transactions_list:
                        categorized_txns, cat_errors = categorize_transactions(fetched_transactions_list)
                        context['errors'].extend(cat_errors) # Add errors from categorization

                        new_count = save_transactions_to_db(request.user, categorized_txns)

                        if new_count > 0:
                            messages.success(request, f"Successfully added {new_count} new transaction(s) from {user_bank} Bank.")
                            # Re-fetch all, sort, and update context
                            all_stored_txns_qs = StoredTransaction.objects.filter(user=request.user)
                            sorted_all_stored_txns = sorted(list(all_stored_txns_qs), key=_parse_transaction_date, reverse=True)
                            context['transactions'] = [txn.transaction_data for txn in sorted_all_stored_txns]
                        else: # new_count is 0
                            messages.info(request, f"No new transactions were added from {user_bank} Bank. Displaying existing data.")
                            # Existing data (if any) is already in context['transactions'] and sorted from initial load.
                            # If previously no transactions, context['transactions'] is still [].
                        
                        context['last_fetch'] = current_fetch_time

                    elif not fetch_errors: # No transactions fetched, and no explicit errors from get_transactions
                        messages.info(request, f"No transactions found in your emails for {user_bank} Bank during this fetch attempt.")
                        context['last_fetch'] = current_fetch_time
                    
                    # If fetch_errors occurred, they are in context['errors'] and a generic message is shown below
                    if fetch_errors:
                         messages.error(request, "There were errors during the transaction fetching process. See details if provided.")


                except Exception as e:
                    error_msg = f"An unexpected error occurred during transaction processing: {e}"
                    print(f"ERROR: {error_msg}")
                    messages.error(request, error_msg)
                    context['errors'].append(error_msg)
        else: # Form is not valid
            messages.error(request, "Invalid App Password entered. Please correct the errors below.")
    
    # For GET request, context['form'] is already set to a new AppPasswordForm()

    # The template should handle an empty context['transactions'] list gracefully.
    template_name = 'emailparser/display_fetched_expenses.html'
    
    return render(request, template_name, context)