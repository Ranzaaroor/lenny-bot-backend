import functions_framework
import os
import json
import gspread
from datetime import datetime

# --- CONFIGURATION ---
# We use environment variables so we don't hardcode secrets
SHEET_ID = os.environ.get('SHEET_ID')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'MY_TEST_TOKEN')


# --- HELPER: WRITE TO SHEET ---
def write_to_journal(author, message):
    try:
        # Authenticate using the uploaded credentials.json
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet("Journal")  # Make sure your tab is named "Journal"

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        # Append the row
        worksheet.append_row([date_str, time_str, author, message])
        print(f"✅ Saved entry from {author}")
        return True
    except Exception as e:
        print(f"❌ Error writing to sheet: {e}")
        return False


# --- MAIN CLOUD FUNCTION ---
@functions_framework.http
def lenny_webhook(request):
    # 1. SETUP: GET REQUEST (Meta Verification Handshake)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                return challenge, 200
            else:
                return 'Forbidden', 403

    # 2. ACTION: POST REQUEST (Incoming Messages)
    if request.method == 'POST':
        data = request.get_json()

        # A. MANUAL TEST TRIGGER (For you to test while waiting for Meta)
        # We can simulate a message by sending a manual CURL request
        if "test_message" in data:
            success = write_to_journal("Test_Dad", data["test_message"])
            return ("Saved to Sheet", 200) if success else ("Failed", 500)

        # B. REAL WHATSAPP LOGIC
        try:
            # Navigate the complex WhatsApp JSON structure
            if 'messages' in data['entry'][0]['changes'][0]['value']:
                message_data = data['entry'][0]['changes'][0]['value']['messages'][0]

                # Extract simple text
                if message_data['type'] == 'text':
                    text_body = message_data['text']['body']
                    sender = message_data['from']

                    # Map phone number to name (optional)
                    # You can map this later or just save the phone number
                    author = "Dad" if "123456" in sender else "Mom"

                    write_to_journal(author, text_body)

        except (KeyError, IndexError):
            # Pass on status updates (read receipts, etc.)
            pass

        return 'OK', 200