import functions_framework
import os
import json
import gspread
import requests
from datetime import datetime

# Import the new client for Secret Manager
from google.cloud import secretmanager

# --- CONFIGURATION (Reads from Cloud Run Environment Variables) ---
SHEET_ID = os.environ.get('SHEET_ID')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN') 
SECRET_NAME = os.environ.get('SECRET_NAME', 'SHEETS_WRITER_KEY_JSON')
# GOOGLE_CLOUD_PROJECT is automatically set by Cloud Run
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT') 

# Initialize the Secret Manager client outside the function (for speed)
# This client object is initialized once when the instance starts
secret_client = secretmanager.SecretManagerServiceClient()


# --- HELPER: RETRIEVE SECRET ---
def get_secret_value(secret_id):
    """Fetches the secret value from Secret Manager."""
    try:
        # Build the resource name to access the latest version of the secret
        resource_name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
        
        # Access the secret version
        response = secret_client.access_secret_version(name=resource_name)
        
        # Decode and return the JSON string payload
        return response.payload.data.decode('UTF-8')
    except Exception as e:
        print(f"FATAL: Could not access secret {secret_id}. Check IAM permissions. Error: {e}")
        raise e


# --- HELPER: WRITE TO SHEET ---
def write_to_journal(author, message):
    """Retrieves key and writes data to the Google Sheet."""
    try:
        # 1. Retrieve the JSON key string from Secret Manager
        credentials_json_string = get_secret_value(SECRET_NAME)
        
        # 2. Convert the JSON string into a Python dictionary
        credentials_dict = json.loads(credentials_json_string) 
        
        # 3. Authenticate using the dictionary (keyless authentication)
        gc = gspread.service_account_from_dict(credentials_dict)
        
        # Open the specific Sheet and Worksheet
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet("Journal") 
        
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
        

# --- MAIN CLOUD FUNCTION (Webhook Handler) ---
@functions_framework.http
def lenny_webhook(request):
    # 1. SETUP: GET REQUEST (Meta Verification Handshake)
    if request.method == 'GET':
        # ... (rest of your GET verification logic) ...
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
        
        # --- (Your WhatsApp/Message Parsing Logic Goes Here) ---
        try:
            # Assuming basic text message extraction (You can expand this later)
            message_value = data['entry'][0]['changes'][0]['value']
            if 'messages' in message_value:
                message_data = message_value['messages'][0]
                
                if message_data['type'] == 'text':
                    text_body = message_data['text']['body']
                    sender = message_data['from'] 
                    
                    # NOTE: Update the PARENTS map here or use a dictionary lookup
                    author = sender 
                    
                    write_to_journal(author, text_body)
                    
        except (KeyError, IndexError, TypeError):
            # Ignore status updates, read receipts, or non-message events
            pass 
            
        return 'OK', 200

# Placeholder for the daily reminder function (requires WhatsApp Template logic)
# def send_daily_reminder(request):
#     # ... (Will use the WHATSAPP_TOKEN and send template) ...
#     pass

# --- ADD THIS TO THE END OF main.py ---
# --- Add this to the very bottom of main.py ---
if __name__ == "__main__":
    import os
    from flask import Flask
    from functions_framework import create_app

    # Cloud Run injects the PORT environment variable (defaulting to 8080)
    port = int(os.environ.get("PORT", 8080))
    
    # Create the app using the handler defined in your file
    app = create_app(target="lenny_webhook")
    
    # Listening on 0.0.0.0 is mandatory for Cloud Run
    app.run(host="0.0.0.0", port=port)