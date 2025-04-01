# emailparser/views.py

import os
from django.shortcuts import render
from .email_utils import get_transactions
import joblib
import nltk
from django.conf import settings

# --- NLTK Download Check (Keep as is) ---
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

# --- Model Loading (Keep as is) ---
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
        'submitted': False, # Flag to know if form was submitted
        'email_used': ''    # To display which email was attempted
    }

    email_user = None
    email_pass = None

    if request.method == 'POST':
        context['submitted'] = True # Mark that the form was submitted
        email_user = request.POST.get('email_address')
        email_pass = request.POST.get('app_password')
        context['email_used'] = email_user or "Not Provided" # Store for display

        if not email_user or not email_pass:
            context['errors'].append("Email address and App Password are required.")
        else:
            # --- Credentials provided, proceed with fetching ---
            print(f"DEBUG: Fetching transactions for {email_user} via form...")
            result = get_transactions(email_user, email_pass) # Fetch transactions
            context['transactions'] = result.get('transactions')
            context['errors'].extend(result.get('errors', [])) # Add fetch errors

            # --- VVV AUTO-CATEGORIZATION VVV ---
            if context['transactions'] and MODEL:
                print("DEBUG: Attempting auto-categorization...")
                for txn in context['transactions']:
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
                        error_msg = f"Error categorizing '{description}': {e}"
                        print(f"ERROR: {error_msg}")
                        if error_msg not in context['errors']:
                            context['errors'].append(error_msg)

            elif context['transactions'] and not MODEL:
                 if MODEL_LOAD_ERROR and MODEL_LOAD_ERROR not in context['errors']:
                     context['errors'].append(MODEL_LOAD_ERROR)
                     print("WARN: Transactions fetched, but model loading failed. Categorization skipped.")
            # --- ^^^ END AUTO-CATEGORIZATION ^^^ ---
            # --- End Fetching Logic ---

    # If GET request, or POST with missing fields (handled above),
    # just render the template. The context will have submitted=False for GET,
    # or submitted=True and errors for invalid POST.
    template_name = 'emailparser/fetch_page.html'
    return render(request, template_name, context)