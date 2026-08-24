"""
Cisco Umbrella S3 Log Downloader
--------------------------------
This script connects directly to the Cisco-managed AWS S3 bucket using your API credentials.
Its purpose is to download the raw, GZIP-compressed CSV log files exactly as Cisco generates them.
This allows you to verify the raw CSV data structure (column headers, metadata) without needing 
Splunk or the Cisco Dashboard to parse it first. 

Usage: 
1. Ensure boto3 is installed (pip install boto3)
2. Enter your S3 credentials below.
3. Uncomment the specific log type you want to download in the PREFIX section.
"""

import boto3
import os

# Connect to Cisco's S3 Bucket using your decrypted keys
s3 = boto3.client('s3', 
    aws_access_key_id='YOUR_ACCESS_KEY_HERE',
    aws_secret_access_key='YOUR_SECRET_KEY_HERE',
    region_name='ap-southeast-1'
)

BUCKET = 'cisco-managed-ap-southeast-1'

# ---------------------------------------------------------
# LOG TYPE SELECTION
# Uncomment the specific log folder you want to download from.
# ---------------------------------------------------------
ORG_PREFIX = '8319904_750a0db0111feb0665b24a046de466ffae180140/'

PREFIX = ORG_PREFIX + 'proxylogs/'        # Web activity logs
# PREFIX = ORG_PREFIX + 'dnslogs/'          # DNS activity logs
# PREFIX = ORG_PREFIX + 'auditlogs/'        # Admin audit logs
# PREFIX = ORG_PREFIX + 'ipfirewalllogs/'   # IP Firewall logs

log_type_name = PREFIX.split('/')[-2].upper()
print(f"Fetching list of {log_type_name} files from Cisco S3...")

response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)

# Get the first file in the bucket
files = response.get('Contents', [])
if not files:
    print(f"No logs found in {log_type_name} yet!")
else:
    first_file_key = files[0]['Key']
    filename = os.path.basename(first_file_key)
    
    print(f"Found log file: {first_file_key}")
    print(f"Downloading to current folder as {filename}...")
    
    # Download the file
    s3.download_file(BUCKET, first_file_key, filename)
    print("Download complete! Unzip it to see the raw CSV logs.")
