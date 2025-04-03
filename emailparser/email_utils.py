# emailparser/email_utils.py
import imaplib
import email
import re
import datetime
from email.header import decode_header

# Define bank-specific email patterns
BANK_PATTERNS = {
    'HDFC': {
        'from_email': "alerts@hdfcbank.net",
        # Group 0: Amount, 1: VPA, 2: Party Name (potentially), 3: Date (YY)
        'upi_pattern': r"Rs\.\s?([\d,]+\.\d{2})\s?has been debited .*? to VPA (\S+)\s*(.*?)\s*on (\d{2}-\d{2}-\d{2})" # Made party name capture non-greedy and handle spaces around it
    },
    'ICICI': {
        'from_email': "alerts@icicibank.com",
        # Group 0: Amount, 1: VPA, 2: Date (YY), 3: Party Name (potentially)
        'upi_pattern': r"Rs\.([\d,]+\.\d{2}) debited from a/c.*?to (\S+).*?on (\d{2}-\d{2}-\d{2})\s+(.*?)\s+" # Added comma support
    },
    'SBI': {
        'from_email': "cbsalerts.sbi@alerts.sbi.co.in",
        # IMPORTANT: THIS IS A CREDIT PATTERN EXAMPLE. Need a DEBIT one.
        # Assuming a hypothetical DEBIT pattern like: "Acct XX1234 Debited INR 100.00 on 03/04/25 ref UPI/..."
        # Let's create a placeholder DEBIT pattern (NEEDS VERIFICATION WITH ACTUAL SBI DEBIT EMAILS)
        # Group 0: Amount, 1: Date (YY), 2: Reference/Info
        'upi_pattern': r"Debited\s+(?:INR|Rs\.?)\s*([\d,]+\.\d{2})\s+on\s+(\d{2}/\d{2}/\d{2}).*?(?:ref|Info)[:\s]*(.*)" # Example Debit Pattern
        # Original Credit Pattern (kept for reference):
        # 'upi_pattern': r"Your A/C .*? has credit for UPI/.*?/(\d{2}/\d{2}/\d{4})/ of Rs (\d+\.\d{2}) on (\d{2}/\d{2}/\d{2})" # G0:Date(YYYY), G1:Amount, G2:Date(YY)
    },
    'AXIS': {
        'from_email': "alerts@axisbank.com",
        # Use the complex pattern to capture structured info
        # Group 0: Amount, 1: Date (YY), 2: Time, 3: Transaction Info
        'upi_pattern': r"Amount Debited:\s*(?:INR|Rs\.?)\s*([\d,]+\.\d{2})\s*.*?Date & Time:\s*(\d{2}-\d{2}-\d{2})\s*,\s*(\d{2}:\d{2}:\d{2})\s*(?:IST)?\s*.*?Transaction Info:\s*([^\r\n]*)"
    },
    'KOTAK': {
        'from_email': "noreply@kotak.com",
        # Group 0: Amount, 1: Reference, 2: Party Name, 3: Date (YY)
        'upi_pattern': r"Rs\.([\d,]+\.\d{2}) has been debited.*?UPI-(\S+).*?to (.+?) on (\d{2}-\d{2}-\d{2})" # Added comma support
    }
}

# Default patterns (Consider removing if all supported banks have specific patterns)
# DEFAULT_UPI_PATTERN = r"Rs\.\s?([\d,]+\.\d{2})\s?has been debited .*? to VPA (\S+)\s*(.*?)\s*on (\d{2}-\d{2}-\d{2})" # Made party capture non-greedy

# connect_gmail function remains the same
def connect_gmail(email_user, email_pass):
    """Connects to Gmail IMAP server."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_user, email_pass)
        mail.select("inbox")
        return mail
    except imaplib.IMAP4.error as e:
        if "AUTHENTICATIONFAILED" in str(e):
             raise ValueError("Authentication failed. Check email/password or App Password.")
        raise ConnectionError(f"Error connecting to Gmail: {e}")
    except Exception as e:
        raise ConnectionError(f"An unexpected error occurred during connection: {e}")


# MODIFIED to accept bank parameter and use bank-specific patterns
def fetch_bank_upi_transactions(mail, bank='HDFC'):
    """Fetches and parses UPI transaction emails for the specified bank."""
    transactions = []
    errors = []
    today = datetime.date.today()
    first_day_of_month = today.replace(day=1)
    search_since_date = first_day_of_month.strftime("%d-%b-%Y")

    if bank in BANK_PATTERNS:
        from_email = BANK_PATTERNS[bank]['from_email']
        upi_pattern = BANK_PATTERNS[bank]['upi_pattern']
        print(f"DEBUG: Using {bank} bank patterns with from_email={from_email}")
        print(f"DEBUG: Pattern for {bank}: {upi_pattern}") # Print the pattern being used
    else:
        # Consider raising an error or handling this more explicitly if defaults aren't desired
        errors.append(f"ERROR: Bank '{bank}' not recognized. No pattern defined.")
        print(f"ERROR: Bank '{bank}' not recognized. Cannot process.")
        # Returning early as we don't have a pattern
        return [], errors # Or handle differently (e.g., use a generic pattern if you define one)
        # from_email = "alerts@hdfcbank.net" # Default HDFC (Removed - better to error if undefined)
        # upi_pattern = DEFAULT_UPI_PATTERN

    search_query = f'(FROM "{from_email}" SINCE "{search_since_date}")'
    print(f"DEBUG: Searching emails with query: {search_query}")

    try:
        result, data = mail.search(None, search_query)
        if result != 'OK':
            raise ConnectionError(f"Failed to search emails: {result}")

        email_ids = data[0].split()
        print(f"DEBUG: Found {len(email_ids)} email IDs for {bank} bank.")

        if not email_ids:
             # Changed to info message instead of error
            print(f"INFO: No emails found from {bank} since {search_since_date}.")
            return [], [] # Return empty lists, not an error

        for e_id in email_ids:
            email_id_str = e_id.decode()
            print(f"\n--- DEBUG: Processing Email ID: {email_id_str} ---")
            try:
                res, msg_data = mail.fetch(e_id, "(RFC822)")
                if res != 'OK':
                    errors.append(f"Failed to fetch email ID {email_id_str}: {res}")
                    print(f"DEBUG: Failed to fetch email {email_id_str}: {res}")
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # --- Header Logging (same as before) ---
                subject_header = msg.get('Subject', 'No Subject Header')
                try:
                    subject, encoding = decode_header(subject_header)[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or 'utf-8', errors='replace')
                except Exception:
                    subject = subject_header
                print(f"  DEBUG: Subject: {subject}")
                print(f"  DEBUG: Content-Type (Main): {msg.get_content_type()}")
                print(f"  DEBUG: Is Multipart: {msg.is_multipart()}")

                # --- Email Body Extraction (robust version from previous code) ---
                email_text = ""
                # ... (Keep your robust multipart/non-multipart text extraction logic here) ...
                # --- Make sure this part correctly populates 'email_text' ---
                if msg.is_multipart():
                    print("  DEBUG: Iterating through parts:")
                    part_found = False
                    for i, part in enumerate(msg.walk()):
                        ctype = part.get_content_type()
                        cdispo = str(part.get("Content-Disposition"))
                        charset = part.get_content_charset()
                        print(f"    DEBUG: Part {i}: Content-Type={ctype}, Disposition={cdispo}, Charset={charset}")

                        if ctype == "text/plain" and "attachment" not in cdispo:
                            print(f"    DEBUG: Part {i}: Attempting to decode text/plain...")
                            try:
                                payload = part.get_payload(decode=True)
                                detected_charset = charset or 'utf-8'
                                print(f"      DEBUG: Decoding with charset: {detected_charset}")
                                email_text = payload.decode(detected_charset, errors="replace")
                                print(f"      DEBUG: Decoded successfully (text/plain). Length: {len(email_text)}")
                                part_found = True
                                break
                            except Exception as decode_err:
                                errors.append(f"Error decoding text/plain part in email ID {email_id_str}: {decode_err}")
                                print(f"      DEBUG: ERROR decoding text/plain: {decode_err}")

                        elif ctype == "text/html" and "attachment" not in cdispo and not part_found:
                            print(f"    DEBUG: Part {i}: Attempting to decode text/html...")
                            try:
                                payload = part.get_payload(decode=True)
                                detected_charset = charset or 'utf-8'
                                print(f"      DEBUG: Decoding with charset: {detected_charset}")
                                email_text_html = payload.decode(detected_charset, errors="replace") # Store temporarily
                                print(f"      DEBUG: Decoded successfully (text/html). Length: {len(email_text_html)}")
                                if not email_text: # Use HTML only if plain text hasn't been found yet
                                     email_text = email_text_html # Assign HTML content
                                     # Optionally strip HTML tags here if needed using a library like BeautifulSoup
                                     # from bs4 import BeautifulSoup
                                     # soup = BeautifulSoup(email_text_html, 'html.parser')
                                     # email_text = soup.get_text()
                                     # print(f"      DEBUG: Stripped HTML to text. New Length: {len(email_text)}")
                                part_found = True
                            except Exception as decode_err:
                                errors.append(f"Error decoding/parsing text/html part in email ID {email_id_str}: {decode_err}")
                                print(f"      DEBUG: ERROR decoding/parsing text/html: {decode_err}")
                else: # Not multipart
                     print("  DEBUG: Attempting to decode non-multipart payload...")
                     try:
                        payload = msg.get_payload(decode=True)
                        charset = msg.get_content_charset() or 'utf-8'
                        print(f"    DEBUG: Decoding with charset: {charset}")
                        email_text = payload.decode(charset, errors="replace")
                        print(f"    DEBUG: Decoded successfully (non-multipart). Length: {len(email_text)}")
                     except Exception as decode_err:
                         errors.append(f"Error decoding non-multipart payload in email ID {email_id_str}: {decode_err}")
                         print(f"    DEBUG: ERROR decoding non-multipart payload: {decode_err}")

                # --- Check if text was extracted ---
                if not email_text:
                    if not any(err for err in errors if f"email ID {email_id_str}" in err and "decoding" in err):
                        errors.append(f"Could not extract text content from email ID {email_id_str}.")
                    print(f"  DEBUG: FAILED to extract any usable text content for email ID {email_id_str}.")
                    continue

                # --- Parsing Logic ---
                print(f"  DEBUG: Extracted text length: {len(email_text)}. Preparing for regex match with {bank} pattern...")
                # print(f"  DEBUG: Text Snippet for Regex: {repr(email_text[:500])}...") # Optional: Print beginning of text

                # --- AXIS BANK Specific Handling using re.search ---
                if bank == 'AXIS':
                    print(f"  DEBUG: [AXIS SPECIFIC] Using re.search with pattern: {upi_pattern}")
                    # Use re.search for the single structured block expected in Axis emails
                    # Use re.DOTALL because the pattern uses .*? which needs to span lines
                    # Use re.IGNORECASE for flexibility with INR/Rs
                    match_obj = re.search(upi_pattern, email_text, re.DOTALL | re.IGNORECASE)

                    if match_obj:
                        print("    DEBUG: [AXIS SPECIFIC] re.search Found a match!")
                        print(f"      DEBUG: Match Group 0 (Full Matched Text): {repr(match_obj.group(0))}") # See what exactly matched
                        print(f"      DEBUG: Match Group 1 (Amount String): {repr(match_obj.group(1))}")
                        print(f"      DEBUG: Match Group 2 (Date): {repr(match_obj.group(2))}")
                        print(f"      DEBUG: Match Group 3 (Time): {repr(match_obj.group(3))}")
                        print(f"      DEBUG: Match Group 4 (Transaction Info): {repr(match_obj.group(4))}")
                        try:
                            amount_str = match_obj.group(1).replace(',', '') # Remove commas
                            amount = float(amount_str)
                            date_str = match_obj.group(2) # Date format DD-MM-YY
                            time_str = match_obj.group(3)
                            tx_info = match_obj.group(4).strip()

                            # Attempt to parse VPA/Party from tx_info if it's UPI related
                            vpa_id = "N/A"
                            party_name = tx_info # Default to full info
                            if tx_info.lower().startswith("upi"):
                                parts = tx_info.split('/')
                                if len(parts) >= 4:
                                    # Heuristic: VPA or name might be the last part
                                    party_name = parts[-1].strip()
                                    # Try to find something looking like a VPA in other parts
                                    for part in parts[:-1]: # Check parts before the last one
                                        if '@' in part:
                                            vpa_id = part.strip()
                                            break
                                elif len(parts) > 1 : # Fallback if less structure
                                    party_name = parts[-1].strip()

                            transactions.append({
                                "date": date_str,
                                "amount": amount,
                                "vpa_id": vpa_id, # Extracted or N/A
                                "party_name": party_name, # Extracted or full info
                                "bank": bank,
                                "time": time_str # Optional: include time
                            })
                            print(f"    DEBUG: [AXIS] Parsed Transaction: Date={date_str}, Amount={amount}, VPA={vpa_id}, Party={party_name}, Bank={bank}, Time={time_str}")
                        except Exception as parse_err:
                            errors.append(f"Error parsing AXIS match in email ID {email_id_str}: {parse_err}")
                            print(f"    DEBUG: [AXIS] ERROR parsing regex match: {parse_err}")
                            print(f"      Raw groups causing error: {match_obj.groups()}") # Print groups on error
                    else:
                        print(f"  DEBUG: [AXIS SPECIFIC] re.search found NO match for the pattern in extracted text.")

                # --- Logic for OTHER BANKS using re.findall ---
                else:
                    print(f"  DEBUG: Using re.findall for {bank} bank with pattern: {upi_pattern}")
                    # Add flags for other banks too, DOTALL is often needed if patterns use .*?
                    matches = re.findall(upi_pattern, email_text, re.DOTALL | re.IGNORECASE)

                    if matches:
                        print(f"  DEBUG: Found {len(matches)} regex match(es) for {bank} pattern (using findall).")
                        for i, match_tuple in enumerate(matches):
                            print(f"    DEBUG: Raw Match Tuple {i+1} for {bank}: {match_tuple}") # Print the raw tuple
                            try:
                                # Reset variables for each match
                                amount, vpa_id, party_name, date_str = None, "N/A", "N/A", None

                                # --- Adjust indices based on specific bank pattern's capture groups ---
                                if bank == 'HDFC': # Groups: 0=Amount, 1=VPA, 2=Party, 3=Date
                                    amount = float(match_tuple[0].replace(',', ''))
                                    vpa_id = match_tuple[1]
                                    party_name = ' '.join(match_tuple[2].strip().lower().split()) if match_tuple[2] else "N/A"
                                    date_str = match_tuple[3] # DD-MM-YY
                                elif bank == 'ICICI': # Groups: 0=Amount, 1=VPA, 2=Date, 3=Party
                                    amount = float(match_tuple[0].replace(',', ''))
                                    vpa_id = match_tuple[1]
                                    date_str = match_tuple[2] # DD-MM-YY
                                    party_name = ' '.join(match_tuple[3].strip().lower().split()) if match_tuple[3] else "N/A"
                                elif bank == 'SBI': # Using placeholder DEBIT pattern: G0=Amount, G1=Date(YY), G2=Info
                                    amount = float(match_tuple[0].replace(',', ''))
                                    date_str = match_tuple[1] # DD/MM/YY
                                    # Attempt to extract VPA/Party from Info (Group 2) if possible
                                    tx_info = match_tuple[2].strip()
                                    party_name = tx_info # Default to full info
                                    vpa_id = "N/A (SBI Format)"
                                    # Add logic here to parse VPA from tx_info if pattern exists
                                    if "upi/" in tx_info.lower():
                                        parts = tx_info.split('/')
                                        for part in parts:
                                            if '@' in part:
                                                vpa_id = part.strip()
                                                break
                                        # Try to get party name heuristic
                                        if len(parts) > 1 :
                                             party_name = parts[-1].strip()

                                elif bank == 'KOTAK': # Groups: 0=Amount, 1=Reference, 2=Party, 3=Date
                                    amount = float(match_tuple[0].replace(',', ''))
                                    vpa_id = "N/A" # Reference (match_tuple[1]) is captured but maybe not VPA
                                    party_name = ' '.join(match_tuple[2].strip().lower().split()) if match_tuple[2] else "N/A"
                                    date_str = match_tuple[3] # DD-MM-YY
                                    # You could try checking match_tuple[1] for '@' if it might contain VPA sometimes

                                # Append transaction if amount and date were found
                                if amount is not None and date_str is not None:
                                    transactions.append({
                                        "date": date_str,
                                        "amount": amount,
                                        "vpa_id": vpa_id,
                                        "party_name": party_name,
                                        "bank": bank
                                    })
                                    print(f"    DEBUG: Parsed Transaction ({bank}): Date={date_str}, Amount={amount}, VPA={vpa_id}, Party={party_name}, Bank={bank}")
                                else:
                                     print(f"    DEBUG: Skipping match for {bank} due to missing Amount or Date. Raw tuple: {match_tuple}")

                            except IndexError as ie:
                                errors.append(f"Index Error parsing {bank} match in email ID {email_id_str}. Pattern mismatch likely. Match: {match_tuple}. Error: {ie}")
                                print(f"    DEBUG: INDEX ERROR parsing {bank} match. Pattern groups don't match code. Match: {match_tuple}. Error: {ie}")
                            except ValueError as ve:
                                errors.append(f"Value Error (likely amount conversion) parsing {bank} match in email ID {email_id_str}. Match: {match_tuple}. Error: {ve}")
                                print(f"    DEBUG: VALUE ERROR parsing {bank} match (Amount Conversion?). Match: {match_tuple}. Error: {ve}")
                            except Exception as parse_err:
                                errors.append(f"General Error parsing {bank} match in email ID {email_id_str}. Match: {match_tuple}. Error: {parse_err}")
                                print(f"    DEBUG: GENERAL ERROR parsing {bank} match. Match: {match_tuple}. Error: {parse_err}")
                    else:
                        print(f"  DEBUG: No pattern match found for {bank} in extracted text (using findall).")

            except Exception as process_err:
                errors.append(f"Error processing email ID {email_id_str}: {process_err}")
                print(f"  DEBUG: UNEXPECTED error processing email {email_id_str}: {process_err}")

        print("\n--- DEBUG: Email processing finished ---")
        return transactions, errors

    except Exception as search_err:
         print(f"DEBUG: ERROR during initial email search/fetch: {search_err}")
         errors.append(f"Error during email search/fetch setup: {search_err}")
         return [], errors
    finally:
        # Logout logic remains the same
        # ... (keep your existing finally block) ...
        if mail:
            try:
                print("DEBUG: Logging out from Gmail.")
                mail.logout()
            except Exception as logout_err:
                 print(f"DEBUG: Error during logout (ignored): {logout_err}")


# get_transactions function remains the same
def get_transactions(email_user, email_pass, bank='HDFC'):
    """Main function to connect, fetch, parse, and return results."""
    try:
        print(f"\nDEBUG: Attempting to connect to Gmail for {bank} bank transactions...")
        mail = connect_gmail(email_user, email_pass)
        print(f"DEBUG: Connection successful. Fetching {bank} transactions...")
        transactions, errors = fetch_bank_upi_transactions(mail, bank) # Pass bank parameter
        print(f"DEBUG: Fetching complete. Transactions: {len(transactions)}, Errors: {len(errors)}")
        # Optionally print errors if any occurred during processing
        if errors:
            print("DEBUG: Errors encountered during fetching:")
            for error in errors:
                print(f"  - {error}")
        return {"transactions": transactions, "errors": errors, "success": True}
    except (ValueError, ConnectionError) as e:
        print(f"DEBUG: Connection/Authentication Error: {e}")
        return {"transactions": [], "errors": [str(e)], "success": False}
    except Exception as e:
        import traceback # Import traceback for detailed error logging
        print(f"DEBUG: An unexpected error occurred in get_transactions: {e}")
        print(f"DEBUG: Traceback:\n{traceback.format_exc()}") # Print full traceback
        return {"transactions": [], "errors": [f"An unexpected error occurred: {e}"], "success": False}