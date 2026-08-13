# Cisco SSE S3 Key Rotation Automation (Zero-Trust Splunk Sync)

## Overview
This repository contains a production-ready Python automation system for rotating Cisco Secure Access (SSE) S3 log exfiltration keys. It is specifically designed to handle the "Self-Healing" of Splunk environments where the UI-based configuration fails due to restricted S3 bucket permissions (`s3:ListBucket`).

The system implements a **Split-Custody Delivery Model**, ensuring that no single individual or channel holds both the encrypted credentials and the decryption key.

## Key Features
- **Automated Rotation**: Fetches fresh S3 keys via Cisco SSE REST APIs.
- **Self-Healing Splunk Integration**: Directly injects credentials into Splunk `.conf` files, bypassing UI validation errors.
- **Zero-Trust Encryption**: Encrypts credentials using AES-128 (Fernet) before distribution.
- **Split-Custody Delivery**: Multi-channel distribution (Discord, LINE, Email) separating the data (locked box) from the key.
- **Stateless Execution**: Deletes all sensitive artifacts from the server immediately after delivery.
- **Firewall Friendly**: Uses HTTPS (Port 443) for all notifications, avoiding SMTP port blocks.

## System Architecture

1.  **Trigger**: Executed via Windows Task Scheduler (e.g., every 90 days).
2.  **Auth & Rotate**: Handshake with `api.sse.cisco.com` to generate new keys.
3.  **Splunk Sync**: Updates `ta_cisco_cloud_security_addon_aws_account.conf` and `ta_cisco_cloud_security_addon_inputs.conf` directly.
4.  **Vaulting**: Generates a unique Fernet Master Key and encrypts the S3 credentials.
5.  **Multi-Channel Delivery**:
    *   **Discord**: Public channel gets the `.enc` file; Private Admin channel gets the Master Key.
    *   **LINE**: User A gets the Base64 data; User B gets the Master Key.
    *   **Email**: Email A gets the `.enc` attachment; Email B gets the Master Key body.
6.  **Cleanup**: Immediate deletion of local encrypted files.

## Setup Instructions

### 1. Prerequisites
- Python 3.13+
- Required Libraries:
  ```bash
  pip install requests cryptography python-dotenv
  ```

### 2. Configuration
Copy the `.env.example` file to `.env` and populate it with your specific credentials and paths:
```bash
cp .env.example .env
```
Ensure the `SPLUNK_..._PATH` variables point to your local Splunk installation's `etc/apps/.../local/` directory.

### 3. Deployment (Windows Server/RDP)
1. Place `s3rotate_final.py` and your `.env` file in a secure directory.
2. Open **Windows Task Scheduler**.
3. Create a new task to run every 90 days.
4. **Important**: Check "Run with highest privileges" (required for file system access to Splunk `.conf` files).

## Usage

### Automation Execution
The script is designed to run unattended:
```bash
python s3rotate_final.py
```

### Manual Decryption
If you need to retrieve the plaintext keys from an encrypted payload:
1. Ensure the `s3_credentials.enc` file is in the same folder as `decrypt_keys.py`.
2. Run the decryption utility:
   ```bash
   python decrypt_keys.py
   ```
3. Paste the **Master Key** provided by the Key Custodian when prompted. The credentials will be displayed in the terminal.

## Security Rationale
This project addresses the risk of credential theft and single-point-of-compromise by:
- Eliminating long-lived plaintext keys on the server.
- Enforcing dual-custody for all key retrievals.
- Utilizing encrypted API-based delivery to bypass restrictive corporate firewalls.

---
ps: There is also a simple version of the script that does not encrypt the keys, refer to s3rotate_Simple.py
---
**Author:** Suttipon Rattana (Blanc)
**Status:** Production Ready
