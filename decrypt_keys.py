from cryptography.fernet import Fernet
import os

def decrypt_file():
    print("--- S3 CREDENTIALS DECRYPTER ---")
    
    # 1. Ask for the Master Key (The one the script printed on the screen)
    master_key = input("Make sure the Encryption file you are trying to decrypt is in the same directory as this decrypting file\nPaste the Master Encryption Key here: ").strip()
    
    # 2. Look for the encrypted file
    filename = "s3_credentials.enc"
    
    if not os.path.exists(filename):
        print(f"Error: Could not find the file '{filename}' in this folder.")
        return

    try:
        # 3. Setup the Decrypter
        f = Fernet(master_key.encode())
        
        # 4. Read and Decrypt
        with open(filename, "rb") as enc_file:
            encrypted_data = enc_file.read()
            
        decrypted_data = f.decrypt(encrypted_data)
        
        print("\n--- DECRYPTED S3 CREDENTIALS ---")
        print(decrypted_data.decode())
        print("--------------------------------")
        
    except Exception as e:
        print(f"Failed to decrypt: {e}")
        print("Double check that you pasted the correct Master Key!")

if __name__ == "__main__":
    decrypt_file()
