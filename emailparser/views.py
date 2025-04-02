# email_parser/views.py

import os
import joblib
import nltk # type: ignore
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required # Import login_required
from django.contrib import messages # Import messages framework
from django.conf import settings
from .email_utils import get_transactions # Your existing email utility
from .forms import AppPasswordForm # Import the form we defined earlier

# --- NLTK Download Check (Keep as is) ---
try:
    nltk.data.find('corpora/stopwords')
    print("DEBUG: NLTK stopwords found.")
except nltk.downloader.DownloadError: # Corrected exception type
    print("DEBUG: NLTK stopwords not found, attempting download...")
    try:
        nltk.download('stopwords')
        print("DEBUG: NLTK stopwords downloaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to download NLTK stopwords: {e}")
# --- End NLTK Check ---

# --- Model Loading (Keep as is, ensure MODEL_PATH is correct) ---
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
# --- End Model Load ---


@login_required # Protect the view, ensure user is logged in
def fetch_and_categorize_expenses(request):
    """
    Handles requesting app password (GET) and fetching/categorizing expenses (POST).
    Uses the logged-in user's email address.
    """
    user_email = request.user.email
    context = {
        'transactions': None,
        'errors': [],
        'model_error': MODEL_LOAD_ERROR, # Pass model loading error to context
        'form': None, # Will hold the AppPasswordForm instance
        'user_email': user_email, # Pass user's email to template
        'show_results': False # Flag to indicate if results should be shown
    }

    # --- Check if user has an email address ---
    if not user_email:
        messages.error(request, "Your account profile needs an email address to fetch transactions.")
        # Redirect to profile editing or home page
        # return redirect('accounts:profile_edit') # Example redirect
        return redirect('home') # Redirect home for now

    # --- Handle POST request (Password submitted) ---
    if request.method == 'POST':
        form = AppPasswordForm(request.POST)
        context['form'] = form # Put form in context even for POST (to show errors)

        if form.is_valid():
            app_password = form.cleaned_data['app_password']
            context['show_results'] = True # Indicate we should try showing results

            # --- Call your existing fetching logic ---
            messages.info(request, f"Attempting to fetch transactions for {user_email}... This may take a moment.")
            print(f"DEBUG: Fetching transactions for {user_email} via trigger view...") # Updated debug log
            try:
                result = get_transactions(user_email, app_password)
                fetched_transactions = result.get('transactions')
                fetch_errors = result.get('errors', [])
                context['transactions'] = fetched_transactions
                context['errors'].extend(fetch_errors)

                # --- Perform Auto-Categorization (if fetch was successful and model loaded) ---
                if fetched_transactions and MODEL:
                    print("DEBUG: Attempting auto-categorization...")
                    for txn in fetched_transactions:
                        try:
                            # Use 'party_name' or adjust if your get_transactions returns a different key
                            description = txn.get('party_name', '')
                            if description:
                                predicted_category = MODEL.predict([description])[0]
                                txn['category'] = predicted_category # Add category to the dict
                                print(f"  DEBUG: Categorized '{description}' as '{predicted_category}'")
                            else:
                                txn['category'] = 'Unknown Description'
                                print("  DEBUG: Skipping categorization for transaction with empty description.")
                        except Exception as e:
                            txn['category'] = 'Categorization Error'
                            error_msg = f"Error categorizing '{description or 'N/A'}': {e}"
                            print(f"ERROR: {error_msg}")
                            if error_msg not in context['errors']:
                                context['errors'].append(error_msg)
                    messages.success(request, "Fetched and categorized transactions.") # Overall success message

                elif fetched_transactions and not MODEL:
                    # Transactions fetched, but model failed to load
                    warn_msg = "Transactions fetched, but auto-categorization is disabled."
                    if MODEL_LOAD_ERROR and MODEL_LOAD_ERROR not in context['errors']:
                       context['errors'].append(MODEL_LOAD_ERROR)
                       warn_msg = f"Transactions fetched, but auto-categorization failed: {MODEL_LOAD_ERROR}"
                    messages.warning(request, warn_msg)
                    print(f"WARN: {warn_msg}")
                    # Assign a default category or None if model isn't working
                    for txn in fetched_transactions:
                        txn['category'] = 'N/A (Model Error)'


                elif not fetched_transactions and not fetch_errors:
                     messages.info(request, "No new transactions found.")

                # Add general success/error messages based on results
                if fetch_errors:
                     messages.error(request, "There were errors fetching transactions. See details below.")


            except Exception as e:
                # Catch unexpected errors during get_transactions or categorization
                error_msg = f"An unexpected error occurred: {e}"
                print(f"ERROR: {error_msg}")
                messages.error(request, error_msg)
                context['errors'].append(error_msg)

            print("\n--- DEBUG VIEW: Final Context Before Rendering Results ---")
            print(f"--- context['transactions']: {context.get('transactions')}") # Use .get for safety
            print(f"--- context['errors']: {context.get('errors')}")
            print(f"--- context['show_results']: {context.get('show_results')}")
            print(f"--- context['model_error']: {context.get('model_error')}")
            print("--------------------------------------------------------\n")

            # --- Render the Results Template ---
            template_name = 'emailparser/display_fetched_expenses.html'
            print(f"DEBUG VIEW: Rendering results template: {template_name}") 
            return render(request, template_name, context)

        else:
            # Form is invalid (e.g., password field empty)
            messages.error(request, "Please enter your App Password.")
            # Fall through to render the password request page again with form errors

    # --- Handle GET request (Show password form) ---
    else: # request.method == 'GET'
        form = AppPasswordForm()
        context['form'] = form

    # For GET requests OR invalid POST requests, render the password request page
    template_name = 'emailparser/request_app_password.html' # Use the password request template
    return render(request, template_name, context)