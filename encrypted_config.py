"""
Encrypted Configuration System
Provides secure storage for sensitive bot data
"""

import os
import base64
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional
import json

class EncryptedConfig:
    def __init__(self):
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            # Generate key if not exists
            self.encryption_key = Fernet.generate_key()
            print(f"🔑 Generated new encryption key: {self.encryption_key.decode()}")
            print("⚠️  Save this key in your environment variables as ENCRYPTION_KEY")
        
        self.cipher = Fernet(self.encryption_key)
        self.config_file = 'config.enc'
    
    def encrypt_data(self, data: Dict[str, Any]) -> str:
        """Encrypt configuration data"""
        json_data = json.dumps(data).encode()
        encrypted_data = self.cipher.encrypt(json_data)
        return base64.b64encode(encrypted_data).decode()
    
    def decrypt_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt configuration data"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.cipher.decrypt(encrypted_bytes)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"❌ Decryption failed: {e}")
            return {}
    
    def save_config(self, config_data: Dict[str, Any]):
        """Save encrypted configuration to file"""
        encrypted_config = self.encrypt_data(config_data)
        with open(self.config_file, 'w') as f:
            f.write(encrypted_config)
        print(f"✅ Configuration encrypted and saved to {self.config_file}")
    
    def load_config(self) -> Dict[str, Any]:
        """Load and decrypt configuration from file"""
        if not os.path.exists(self.config_file):
            print(f"⚠️  Config file {self.config_file} not found")
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                encrypted_data = f.read()
            return self.decrypt_data(encrypted_data)
        except Exception as e:
            print(f"❌ Failed to load config: {e}")
            return {}
    
    def get_secure_value(self, key: str, default: Any = None) -> Any:
        """Get a secure value from encrypted config"""
        config = self.load_config()
        return config.get(key, default)

# Global encrypted config instance
encrypted_config = EncryptedConfig()

# Secure configuration values
SECURE_CONFIG = {
    'BOT_TOKEN': os.getenv('BOT_TOKEN'),
    'MONGO_URL': os.getenv('MONGO_URL'),
    'ADMIN_IDS': [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x],
    'OWNER_ID': int(os.getenv('OWNER_ID', 0)) if os.getenv('OWNER_ID') else None,
    'API_ID': os.getenv('API_ID'),
    'API_HASH': os.getenv('API_HASH'),
    'WEBHOOK_URL': os.getenv('WEBHOOK_URL'),
    'ENCRYPTION_KEY': os.getenv('ENCRYPTION_KEY')
}

def setup_encrypted_config():
    """Setup encrypted configuration"""
    print("🔐 Setting up encrypted configuration...")
    
    # Save current config to encrypted file
    encrypted_config.save_config(SECURE_CONFIG)
    
    print("✅ Encrypted configuration setup complete!")
    print("🔑 Your encryption key:", encrypted_config.encryption_key.decode())
    print("⚠️  Save this key securely and set it as ENCRYPTION_KEY environment variable")

if __name__ == "__main__":
    setup_encrypted_config()
