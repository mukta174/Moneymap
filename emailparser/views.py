# emailparser/views.py

import os
from django.shortcuts import render
from .email_utils import get_transactions
import joblib
import nltk
from django.conf import settings


try:
    nltk.data.find('corpora/stopwords')
    print("DEBUG: NLTK stopwords found.")
except nltk.Downloader.DownloadError:
    print("DEBUG: NLTK stopwords not found, attempting download...")
    try:
        nltk.download('stopwords')
        print("DEBUG: NLTK stopwords downloaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to download NLTK stopwords: {e}")

MODEL_PATH = os.path.join(settings.BASE_DIR, 'expense_classifier.pkl')
MODEL = None
MODEL_LOAD_ERROR = None # To store any loading errors

print(f"DEBUG: Attempting to load model from: {MODEL_PATH}") # Debug print
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
    MODEL = None # Ensure model is None if loading fails
# --- End Model Load ---


def fetch_expenses_view(request):
    context = {
        'transactions': None,
        'errors': [],
        'submitted': False, # Change based on whether you use form or auto-fetch
        'email_used': ''
    }

    # Determine if using manual form or auto-fetch based on your setup
    # This example assumes you might still have the POST logic or are using auto-fetch
    # For auto-fetch using environment variables (as discussed previously):
    use_auto_fetch = True # Set to True if using env vars, False if using form POST

    email_user = None
    email_pass = None

    if use_auto_fetch:
        email_user = os.environ.get('GMAIL_USER_EMAIL')
        email_pass = os.environ.get('GMAIL_APP_PASSWORD')
        context['submitted'] = True # Assume submission if auto-fetching
        if not email_user:
             context['errors'].append("GMAIL_USER_EMAIL environment variable not set.")
        if not email_pass:
             context['errors'].append("GMAIL_APP_PASSWORD environment variable not set.")

    elif request.method == 'POST':
         # Logic for getting email/pass from POST form
         context['submitted'] = True
         email_user = request.POST.get('email_address')
         email_pass = request.POST.get('app_password')
         if not email_user or not email_pass:
             context['errors'].append("Email address and App Password are required.")
    # Add elif for GET if you want the form to show initially without auto-fetch

    context['email_used'] = email_user or "Not Set"

    # Only proceed if we have credentials (either from form or env vars)
    if email_user and email_pass:
        print(f"DEBUG: Fetching transactions for {email_user}...")
        result = get_transactions(email_user, email_pass) # Fetch transactions
        context['transactions'] = result.get('transactions')
        context['errors'].extend(result.get('errors', [])) # Add fetch errors

        # --- VVV AUTO-CATEGORIZATION VVV ---
        if context['transactions'] and MODEL: # Check if fetch was successful AND model loaded
            print("DEBUG: Attempting auto-categorization...")
            for txn in context['transactions']:
                try:
                    # Use 'party_name' as the description for categorization
                    description = txn.get('party_name', '')
                    if description:
                        # Predict expects a list/iterable
                        predicted_category = MODEL.predict([description])[0]
                        txn['category'] = predicted_category # Add category to the dict
                        print(f"  DEBUG: Categorized '{description}' as '{predicted_category}'")
                    else:
                        txn['category'] = 'Unknown Description'
                        print("  DEBUG: Skipping categorization for transaction with empty description.")
                except Exception as e:
                    txn['category'] = 'Categorization Error'
                    error_msg = f"Error categorizing '{description}': {e}"
                    print(f"ERROR: {error_msg}")
                    # Optionally add categorization errors to the main error list
                    if error_msg not in context['errors']:
                        context['errors'].append(error_msg)

        elif context['transactions'] and not MODEL:
             # If fetch worked but model didn't load, add the loading error
             if MODEL_LOAD_ERROR and MODEL_LOAD_ERROR not in context['errors']:
                 context['errors'].append(MODEL_LOAD_ERROR)
                 print("WARN: Transactions fetched, but model loading failed. Categorization skipped.")
        # --- ^^^ END AUTO-CATEGORIZATION ^^^ ---

    elif not context['errors'] and not (use_auto_fetch and request.method != 'POST'):
        # If it's not auto-fetch and not a POST, implies initial GET for the form page
        # Or if auto-fetch setup failed due to missing env vars
        pass # Just render the initial page or error messages already added


    # Select the correct template based on your setup (form vs auto)
    template_name = 'emailparser/fetch_page.html' # Or 'emailparser/fetch_page_auto.html'
    return render(request, template_name, context)