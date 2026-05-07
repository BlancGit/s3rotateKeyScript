import requests
import os
import datetime
import smtplib
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
DISCORD_TEAM_WEBHOOK = os.getenv("DISCORD_TEAM_WEBHOOK")
DISCORD_ADMIN_WEBHOOK = os.getenv("DISCORD_ADMIN_WEBHOOK")

# =========================================================
# 3. SPLUNK CONFIGURATION
# =========================================================
SPLUNK_ACCOUNT_CONFIG_PATH = os.getenv("SPLUNK_ACCOUNT_CONFIG_PATH")
SPLUNK_INPUTS_CONFIG_PATH = os.getenv("SPLUNK_INPUTS_CONFIG_PATH")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_BUCKET_REGION = os.getenv("S3_BUCKET_REGION")
S3_DIRECTORY_PREFIX = os.getenv("S3_DIRECTORY_PREFIX")
SPLUNK_INDEX = os.getenv("SPLUNK_INDEX")

# =========================================================
# 4. LINE CONFIGURATION
# =========================================================
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID_A = os.getenv("LINE_USER_ID_A")
LINE_USER_ID_B = os.getenv("LINE_USER_ID_B")

# =========================================================
# 5. EMAIL CONFIGURATION (SendGrid)
# =========================================================
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL_A = os.getenv("RECIPIENT_EMAIL_A")
RECIPIENT_EMAIL_B = os.getenv("RECIPIENT_EMAIL_B")

def send_sendgrid_email(target_email, subject, body):
    """
    Sends a plaintext email using SendGrid API.
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
            print(f"Failed to send LINE message to {target_uid}. Status: {response.status_code}")
    except Exception as e:
        print(f"Error sending LINE message: {e}")

def update_splunk_config(new_access_key, new_secret_key):
    """
    Updates Splunk Add-on config files with new plaintext keys.
    """
    print("\n--- UPDATING SPLUNK CONFIGURATION ---")
    
    if not SPLUNK_ACCOUNT_CONFIG_PATH or not SPLUNK_INPUTS_CONFIG_PATH:
        print("Warning: Splunk config paths not set. Skipping update.")
        return

    account_content = f"""[Cisco_Managed_S3]
access_key_id = {new_access_key}
secret_access_key = {new_secret_key}
region = {S3_BUCKET_REGION}
"""

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
        with open(SPLUNK_ACCOUNT_CONFIG_PATH, "w") as f:
            f.write(account_content)
        with open(SPLUNK_INPUTS_CONFIG_PATH, "w") as f:
            f.write(input_content)
        print("Success! Splunk configurations updated.")
    except Exception as e:
        print(f"Error updating Splunk config: {e}")

def rotate_keys_simple():
    auth_url = "https://api.sse.cisco.com/auth/v2/token"
    rotate_url = "https://api.sse.cisco.com/admin/v2/iam/rotateKey"
    
    try:
        # 1. ROTATE KEYS
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
        
        print("Keys rotated successfully!")

        # 2. UPDATE SPLUNK
        update_splunk_config(new_access_key, new_secret_key)
        
        # 3. NOTIFY VIA DISCORD
        print("\nSending Discord notifications...")
        notification_text = (
            f"🚀 **Cisco S3 Key Rotation Successful**\n\n"
            f"**Access Key ID:** `{new_access_key}`\n"
            f"**Secret Key:** `{new_secret_key}`\n\n"
            f"Splunk has been updated automatically."
        )
        
        payload = {"content": notification_text}
        if DISCORD_TEAM_WEBHOOK:
            requests.post(DISCORD_TEAM_WEBHOOK, json=payload)
        if DISCORD_ADMIN_WEBHOOK:
            requests.post(DISCORD_ADMIN_WEBHOOK, json=payload)

        # 4. NOTIFY VIA LINE
        print("Sending LINE notifications...")
        line_msg = f"Cisco S3 Keys Rotated\n\nAccess Key: {new_access_key}\nSecret: {new_secret_key}"
        send_line_push(LINE_USER_ID_A, line_msg)
        send_line_push(LINE_USER_ID_B, line_msg)

        # 5. NOTIFY VIA EMAIL (SENDGRID)
        print("Sending Email notifications...")
        email_subject = "ACTION REQUIRED: Cisco S3 Keys Rotated"
        email_body = f"""
        Hello,

        The Cisco S3 keys have been rotated.
        
        Access Key ID: {new_access_key}
        Secret Access Key: {new_secret_key}

        Splunk has been updated automatically.

        Regards,
        S3 Rotation Bot
        """
        send_sendgrid_email(RECIPIENT_EMAIL_A, email_subject, email_body)
        send_sendgrid_email(RECIPIENT_EMAIL_B, email_subject, email_body)
        
        print("\nProcess complete!")

    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    rotate_keys_simple()
