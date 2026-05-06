import requests
import os
import datetime
import base64
import smtplib
from email.message import EmailMessage
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =========================================================
# 1. AUTHENTICATION (Cisco API Keys)
# =========================================================
CLIENT_ID = os.getenv("CISCO_CLIENT_ID")
CLIENT_SECRET = os.getenv("CISCO_CLIENT_SECRET")

# =========================================================
# 2. DISCORD CONFIGURATION
# =========================================================
# PUBLIC CHANNEL: Sends the encrypted file (.enc)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_PUBLIC_WEBHOOK")

# PRIVATE CHANNEL: Sends the Master Key (For Admin/Boss only)
ADMIN_WEBHOOK_URL = os.getenv("DISCORD_ADMIN_WEBHOOK")

# SPLUNK CONFIGURATION
SPLUNK_ACCOUNT_CONFIG_PATH = os.getenv("SPLUNK_ACCOUNT_CONFIG_PATH")
SPLUNK_INPUTS_CONFIG_PATH = os.getenv("SPLUNK_INPUTS_CONFIG_PATH")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_BUCKET_REGION = os.getenv("S3_BUCKET_REGION")
S3_DIRECTORY_PREFIX = os.getenv("S3_DIRECTORY_PREFIX")
SPLUNK_INDEX = os.getenv("SPLUNK_INDEX")

# LINE CONFIGURATION
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID_DATA = os.getenv("LINE_USER_ID_DATA")
LINE_USER_ID_KEY = os.getenv("LINE_USER_ID_KEY")

# EMAIL CONFIGURATION (SendGrid)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL_DATA = os.getenv("RECIPIENT_EMAIL_DATA")
RECIPIENT_EMAIL_KEY = os.getenv("RECIPIENT_EMAIL_KEY")

def send_sendgrid_email(target_email, subject, body, attachment_path=None):
    """
    Sends an email using SendGrid API. Supports split-delivery and attachments.
    """
    if not SENDGRID_API_KEY or not target_email:
        return

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    mail_json = {
        "personalizations": [{"to": [{"email": target_email}]}],
        "from": {"email": SENDER_EMAIL, "name": "S3-Rotation-Bot"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}]
    }

    # Add attachment if provided (e.g. for the .enc file)
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            data = f.read()
            encoded_file = base64.b64encode(data).decode()
        
        mail_json["attachments"] = [{
            "content": encoded_file,
            "filename": os.path.basename(attachment_path),
            "type": "application/octet-stream",
            "disposition": "attachment"
        }]
    
    try:
        response = requests.post(url, headers=headers, json=mail_json)
        if response.status_code in [200, 201, 202]:
            print(f"Success! Email sent to {target_email}")
        else:
            print(f"Failed to send email to {target_email}. Status: {response.status_code}")
    except Exception as e:
        print(f"Error during SendGrid delivery: {e}")

def send_line_push(target_uid, message_text):
    """
    Sends a push notification to a specific LINE User ID.
    """
    if not LINE_ACCESS_TOKEN or not target_uid:
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    payload = {
        "to": target_uid,
        "messages": [{"type": "text", "text": message_text}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"Failed to send LINE message. Status: {response.status_code}, Error: {response.text}")
    except Exception as e:
        print(f"Error sending LINE message: {e}")

def update_splunk_config(new_access_key, new_secret_key):
    """
    Automatically updates the Splunk Add-on configuration files.
    This version uses the exact field names expected by the Cisco Secure Access Add-on UI.
    """
    print("\n--- UPDATING SPLUNK CONFIGURATION ---")
    
    if not SPLUNK_ACCOUNT_CONFIG_PATH or not SPLUNK_INPUTS_CONFIG_PATH:
        print("Warning: Splunk config paths not set in .env. Skipping update.")
        return

    # 1. Update the 'Account' (Credentials)
    account_content = f"""[Cisco_Managed_S3]
access_key_id = {new_access_key}
secret_access_key = {new_secret_key}
region = {S3_BUCKET_REGION}
"""

    # 2. Update the 'Input' (The actual log stream)
    input_content = f"""[dns_logs]
aws_account = Cisco_Managed_S3
aws_region = {S3_BUCKET_REGION}
bucket_name = {S3_BUCKET_NAME}
event_type = dns
index = {SPLUNK_INDEX}
interval = 600
prefix = {S3_DIRECTORY_PREFIX}
start_date = {datetime.datetime.now().strftime("%Y-%m-%d")}
disabled = 0
"""
    
    try:
        # Update Account File
        with open(SPLUNK_ACCOUNT_CONFIG_PATH, "w") as f:
            f.write(account_content)
        print(f"Success! Splunk Account updated: {SPLUNK_ACCOUNT_CONFIG_PATH}")

        # Update Inputs File
        with open(SPLUNK_INPUTS_CONFIG_PATH, "w") as f:
            f.write(input_content)
        print(f"Success! Splunk Inputs updated: {SPLUNK_INPUTS_CONFIG_PATH}")

    except Exception as e:
        print(f"Error updating Splunk config: {e}")

def rotate_keys_discord():
    auth_url = "https://api.sse.cisco.com/auth/v2/token"
    rotate_url = "https://api.sse.cisco.com/admin/v2/iam/rotateKey"
    
    try:
        # --- PART 1: ROTATE KEYS ---
        print("Authenticating with Cisco SSE API...")
        token_resp = requests.post(auth_url, auth=(CLIENT_ID, CLIENT_SECRET), data={"grant_type": "client_credentials"})
        token_resp.raise_for_status()
        token = token_resp.json().get("access_token")
        
        print("Success! Rotating S3 keys...")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        rotate_resp = requests.post(rotate_url, headers=headers)
        rotate_resp.raise_for_status()
        
        new_keys = rotate_resp.json()
        new_access_key = new_keys.get('currentKeyId')
        new_secret_key = new_keys.get('secretAccessKey')
        
        print(f"Keys rotated successfully!")

        # --- NEW PART: UPDATE SPLUNK ---
        update_splunk_config(new_access_key, new_secret_key)
        
        # --- PART 2: ENCRYPTION ---
        print("\n--- ENCRYPTING KEYS ---")
        master_key = Fernet.generate_key()
        f = Fernet(master_key)
        
        sensitive_data = f"Access Key ID: {new_access_key}\nSecret Access Key: {new_secret_key}"
        encrypted_data = f.encrypt(sensitive_data.encode())
        
        encrypted_filename = "s3_credentials.enc"
        with open(encrypted_filename, "wb") as enc_file:
            enc_file.write(encrypted_data)
            
        decoded_master_key = master_key.decode()
        print("="*60)
        print("CRITICAL: MASTER ENCRYPTION KEY (Sending to Admin Channel...)")
        print("="*60)

        # --- PART 3: SEND TO DISCORD ---
        # 1. Send Encrypted File to Public Channel
        print("\nSending encrypted file to Public Discord...")
        
        public_payload = {
            "content": "🚀 **Cisco S3 Key Rotation Successful**\n\nThe keys have been rotated and encrypted. The encrypted payload is attached below.\n\n**Action Required:** Download the file and use the `decrypt_keys.py` utility with the Master Key provided in the private Admin channel."
        }
        
        with open(encrypted_filename, 'rb') as f_upload:
            files = {'file': (encrypted_filename, f_upload)}
            requests.post(DISCORD_WEBHOOK_URL, data=public_payload, files=files)
        
        # 2. Send Master Key to Private Admin Channel
        print("Sending Master Key to Admin Channel...")
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        admin_content = f"🔑 **URGENT: Master Key for S3 Rotation**\n\n**Timestamp:** {current_date}\n\n**Master Key:** `{decoded_master_key}`\n\nUse this key with `decrypt_keys.py` to unlock the latest `s3_credentials.enc` file."
        
        admin_payload = {"content": admin_content}
        requests.post(ADMIN_WEBHOOK_URL, json=admin_payload)
        print("SUCCESS! Master Key delivered to Admin.")

        # --- PART 4: SECURE LINE SPLIT DELIVERY ---
        print("\nPerforming secure split-delivery on LINE...")
        b64_data = base64.b64encode(encrypted_data).decode('utf-8')
        
        line_data_msg = f"📦 S3 ENCRYPTED DATA (Part 1/2)\n\nPayload:\n{b64_data}\n\nNote: This data is useless without the Master Key held by User B."
        send_line_push(LINE_USER_ID_DATA, line_data_msg)
        
        line_key_msg = f"🔑 S3 MASTER KEY (Part 2/2)\n\nKey: {decoded_master_key}\n\nNote: Use this to unlock the data held by User A."
        send_line_push(LINE_USER_ID_KEY, line_key_msg)
        print("SUCCESS! LINE split-delivery complete.")

        # --- PART 5: SECURE EMAIL SPLIT DELIVERY (SENDGRID) ---
        print("\nPerforming secure split-delivery on Email...")

        # A. Send Encrypted File to Recipient A (Data Custodian)
        email_data_subject = "ACTION REQUIRED: S3 Keys Rotated (Encrypted Payload)"
        email_data_body = """
        Hello Admin,

        The Cisco SSE S3 keys have been rotated and encrypted. 
        The encrypted payload is attached to this email.

        Note: This file is useless without the Master Key held by User B.

        Regards,
        S3 Key Rotation Automation
        """
        send_sendgrid_email(RECIPIENT_EMAIL_DATA, email_data_subject, email_data_body, attachment_path=encrypted_filename)

        # B. Send Master Key to Recipient B (Key Custodian)
        email_key_subject = "ACTION REQUIRED: S3 Keys Rotated (Master Key)"
        email_key_body = f"""
        Hello Admin,

        The Cisco SSE S3 keys have been rotated and encrypted.
        
        MASTER ENCRYPTION KEY: {decoded_master_key}
        
        Note: Use this key with 'decrypt_keys.py' to unlock the data held by User A.

        Regards,
        S3 Key Rotation Automation
        """
        send_sendgrid_email(RECIPIENT_EMAIL_KEY, email_key_subject, email_key_body)
        
        print("SUCCESS! Email split-delivery complete.")
        
        # Cleanup
        if os.path.exists(encrypted_filename):
            os.remove(encrypted_filename)
            
        print("\nProcess complete!")

    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    rotate_keys_discord()
