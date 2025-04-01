# emailparser/email_utils.py
import imaplib
import email
import re
import datetime
from email.header import decode_header

# Regex pattern for UPI transactions (same as your script)
UPI_PATTERN = r"Rs\.\s?(\d+\.\d{2})\s?has been debited .*? to VPA (\S+)\s(.+?) on (\d{2}-\d{2}-\d{2})"

# --- connect_gmail function remains the same ---
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


# --- MODIFIED fetch_hdfc_upi_transactions function ---
def fetch_hdfc_upi_transactions(mail):
    """Fetches and parses UPI transaction emails from HDFC for today with enhanced logging."""
    transactions = []
    errors = []
    today = datetime.date.today()
    # Calculate the first day of the current month by replacing the day part with 1
    first_day_of_month = today.replace(day=1)
    # Format the first day for the IMAP search (e.g., "01-May-2024")
    search_since_date = first_day_of_month.strftime("%d-%b-%Y")

    # Construct the search query using the calculated start date
    search_query = f'(FROM "alerts@hdfcbank.net" SINCE "{search_since_date}")'    
    print(f"DEBUG: Searching emails with query: {search_query}") # DEBUG

    try:
        result, data = mail.search(None, search_query)
        if result != 'OK':
            raise ConnectionError(f"Failed to search emails: {result}")

        email_ids = data[0].split()
        print(f"DEBUG: Found {len(email_ids)} email IDs.") # DEBUG

        if not email_ids:
            return [], ["No emails found from HDFC for today."]

        for e_id in email_ids:
            email_id_str = e_id.decode() # Decode once for logging/errors
            print(f"\n--- DEBUG: Processing Email ID: {email_id_str} ---") # DEBUG
            try:
                res, msg_data = mail.fetch(e_id, "(RFC822)")
                if res != 'OK':
                    errors.append(f"Failed to fetch email ID {email_id_str}: {res}")
                    print(f"DEBUG: Failed to fetch email {email_id_str}: {res}") # DEBUG
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Log basic headers
                subject_header = msg.get('Subject', 'No Subject Header')
                try:
                    subject, encoding = decode_header(subject_header)[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or 'utf-8', errors='replace')
                except Exception:
                    subject = subject_header # Fallback to raw header if decoding fails
                print(f"  DEBUG: Subject: {subject}") # DEBUG
                print(f"  DEBUG: Content-Type (Main): {msg.get_content_type()}") # DEBUG
                print(f"  DEBUG: Is Multipart: {msg.is_multipart()}") # DEBUG

                email_text = ""
                if msg.is_multipart():
                    print("  DEBUG: Iterating through parts:") # DEBUG
                    part_found = False
                    for i, part in enumerate(msg.walk()):
                        ctype = part.get_content_type()
                        cdispo = str(part.get("Content-Disposition"))
                        charset = part.get_content_charset()
                        print(f"    DEBUG: Part {i}: Content-Type={ctype}, Disposition={cdispo}, Charset={charset}") # DEBUG

                        # Prefer text/plain
                        if ctype == "text/plain" and "attachment" not in cdispo:
                            print(f"    DEBUG: Part {i}: Attempting to decode text/plain...") # DEBUG
                            try:
                                payload = part.get_payload(decode=True) # Decode Base64/QP
                                detected_charset = charset or 'utf-8' # Default to utf-8 if not specified
                                print(f"      DEBUG: Decoding with charset: {detected_charset}") # DEBUG
                                email_text = payload.decode(detected_charset, errors="replace") # Use replace to see errors
                                print(f"      DEBUG: Decoded successfully (text/plain). Length: {len(email_text)}") # DEBUG
                                part_found = True
                                break # Found plain text, prioritize it
                            except Exception as decode_err:
                                errors.append(f"Error decoding text/plain part in email ID {email_id_str}: {decode_err}")
                                print(f"      DEBUG: ERROR decoding text/plain: {decode_err}") # DEBUG
                                # Don't break, maybe HTML part will work

                        # Fallback to text/html IF no plain text found yet
                        elif ctype == "text/html" and "attachment" not in cdispo and not part_found:
                            print(f"    DEBUG: Part {i}: Attempting to decode text/html...") # DEBUG
                            try:
                                payload = part.get_payload(decode=True)
                                detected_charset = charset or 'utf-8'
                                print(f"      DEBUG: Decoding with charset: {detected_charset}") # DEBUG
                                # SECURITY NOTE: Be cautious rendering raw HTML later. For extraction, it's okay.
                                email_text = payload.decode(detected_charset, errors="replace")
                                print(f"      DEBUG: Decoded successfully (text/html). Length: {len(email_text)}") # DEBUG
                                # Don't break here immediately, maybe a plain text part exists later?
                                # But we store it in case no plain text is found.
                                part_found = True # Mark that we found *some* text part
                            except Exception as decode_err:
                                errors.append(f"Error decoding text/html part in email ID {email_id_str}: {decode_err}")
                                print(f"      DEBUG: ERROR decoding text/html: {decode_err}") # DEBUG

                else: # Not multipart
                     print("  DEBUG: Attempting to decode non-multipart payload...") # DEBUG
                     try:
                        payload = msg.get_payload(decode=True)
                        charset = msg.get_content_charset() or 'utf-8'
                        print(f"    DEBUG: Decoding with charset: {charset}") # DEBUG
                        email_text = payload.decode(charset, errors="replace")
                        print(f"    DEBUG: Decoded successfully (non-multipart). Length: {len(email_text)}") # DEBUG
                     except Exception as decode_err:
                         errors.append(f"Error decoding non-multipart payload in email ID {email_id_str}: {decode_err}")
                         print(f"    DEBUG: ERROR decoding non-multipart payload: {decode_err}") # DEBUG


                if not email_text:
                    # This is the original error point
                    if not any(err for err in errors if f"email ID {email_id_str}" in err and "decoding" in err):
                        # Add the general error only if no specific decoding error was already logged for this email
                         errors.append(f"Could not extract text content from email ID {email_id_str}.")
                    print(f"  DEBUG: FAILED to extract any usable text content for email ID {email_id_str}.") # DEBUG
                    continue # Skip to next email

                # --- Parsing Logic ---
                print(f"  DEBUG: Extracted text length: {len(email_text)}. Attempting regex match...") # DEBUG
                matches = re.findall(UPI_PATTERN, email_text)

                if matches:
                    print(f"  DEBUG: Found {len(matches)} regex match(es).") # DEBUG
                    for match in matches:
                        try:
                            amount = float(match[0])
                            vpa_id = match[1]
                            party_name = ' '.join(match[2].strip().lower().split())
                            date_str = match[3]
                            transactions.append({"date": date_str, "amount": amount, "vpa_id": vpa_id, "party_name": party_name})
                            print(f"    DEBUG: Parsed Transaction: Date={date_str}, Amount={amount}, VPA={vpa_id}, Party={party_name}") # DEBUG
                        except Exception as parse_err:
                            errors.append(f"Error parsing match in email ID {email_id_str}: {parse_err}")
                            print(f"    DEBUG: ERROR parsing regex match: {parse_err}") # DEBUG
                else:
                    print("  DEBUG: No UPI pattern match found in extracted text.") # DEBUG


            except Exception as fetch_err:
                errors.append(f"Error processing email ID {email_id_str}: {fetch_err}")
                print(f"  DEBUG: UNEXPECTED error processing email {email_id_str}: {fetch_err}") # DEBUG

        print("\n--- DEBUG: Email processing finished ---") # DEBUG
        return transactions, errors

    except Exception as search_err:
         print(f"DEBUG: ERROR during initial email search/fetch: {search_err}") # DEBUG
         # Log the error before raising/returning
         errors.append(f"Error during email search/fetch setup: {search_err}")
         # We need to decide how to handle this - raise or return? Returning is safer for web view
         # raise ConnectionError(f"Error during email search/fetch: {search_err}")
         return [], errors # Return empty list and the error
    finally:
        if mail:
            try:
                print("DEBUG: Logging out from Gmail.") # DEBUG
                mail.logout()
            except Exception as logout_err:
                 print(f"DEBUG: Error during logout (ignored): {logout_err}") # DEBUG


# --- get_transactions function remains the same ---
def get_transactions(email_user, email_pass):
    """Main function to connect, fetch, parse, and return results."""
    try:
        print("\nDEBUG: Attempting to connect to Gmail...") # DEBUG
        mail = connect_gmail(email_user, email_pass)
        print("DEBUG: Connection successful. Fetching transactions...") # DEBUG
        transactions, errors = fetch_hdfc_upi_transactions(mail) # mail is implicitly logged out inside fetch
        print(f"DEBUG: Fetching complete. Transactions: {len(transactions)}, Errors: {len(errors)}") # DEBUG
        return {"transactions": transactions, "errors": errors, "success": True}
    except (ValueError, ConnectionError) as e:
        print(f"DEBUG: Connection/Authentication Error: {e}") # DEBUG
        return {"transactions": [], "errors": [str(e)], "success": False}
    except Exception as e:
        print(f"DEBUG: An unexpected error occurred in get_transactions: {e}") # DEBUG
        return {"transactions": [], "errors": [f"An unexpected error occurred: {e}"], "success": False}