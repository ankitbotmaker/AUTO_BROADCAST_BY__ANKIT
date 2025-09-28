"""
Secure Configuration System for Telegram Bot
Provides encryption for sensitive data while maintaining deployment compatibility
"""

import os
import base64
import json
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet

class SecureConfig:
    def __init__(self):
        self.encryption_key = self._get_or_create_key()
        self.cipher = Fernet(self.encryption_key)
        self.encrypted_file = 'secure_config.enc'
    
    def _get_or_create_key(self) -> bytes:
        """Get encryption key from environment or create new one"""
        key = os.getenv('ENCRYPTION_KEY')
        if key:
            return key.encode()
        else:
            # Generate new key
            new_key = Fernet.generate_key()
            print(f"🔑 Generated new encryption key: {new_key.decode()}")
            print("⚠️  Add this to your environment variables: ENCRYPTION_KEY=" + new_key.decode())
            return new_key
    
    def encrypt_data(self, data: Dict[str, Any]) -> str:
        """Encrypt sensitive data"""
        json_data = json.dumps(data).encode()
        encrypted_data = self.cipher.encrypt(json_data)
        return base64.b64encode(encrypted_data).decode()
    
    def decrypt_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt sensitive data"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.cipher.decrypt(encrypted_bytes)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"❌ Decryption failed: {e}")
            return {}
    
    def save_secure_config(self, config_data: Dict[str, Any]):
        """Save encrypted configuration"""
        encrypted_config = self.encrypt_data(config_data)
        with open(self.encrypted_file, 'w') as f:
            f.write(encrypted_config)
        print(f"✅ Secure configuration saved to {self.encrypted_file}")
    
    def load_secure_config(self) -> Dict[str, Any]:
        """Load encrypted configuration"""
        if not os.path.exists(self.encrypted_file):
            return {}
        
        try:
            with open(self.encrypted_file, 'r') as f:
                encrypted_data = f.read()
            return self.decrypt_data(encrypted_data)
        except Exception as e:
            print(f"❌ Failed to load secure config: {e}")
            return {}
    
    def get_secure_value(self, key: str, default: Any = None) -> Any:
        """Get secure value with fallback to environment"""
        # First try environment variable
        env_value = os.getenv(key)
        if env_value:
            return env_value
        
        # Then try encrypted config
        secure_config = self.load_secure_config()
        return secure_config.get(key, default)

# Global secure config instance
secure_config = SecureConfig()

def setup_secure_config():
    """Setup secure configuration with current values"""
    print("🔐 Setting up secure configuration...")
    
    # Get current sensitive values
    sensitive_data = {
        'BOT_TOKEN': os.getenv('BOT_TOKEN'),
        'MONGO_URL': os.getenv('MONGO_URL'),
        'ADMIN_IDS': os.getenv('ADMIN_IDS'),
        'OWNER_ID': os.getenv('OWNER_ID'),
        'API_ID': os.getenv('API_ID'),
        'API_HASH': os.getenv('API_HASH'),
        'WEBHOOK_URL': os.getenv('WEBHOOK_URL')
    }
    
    # Remove None values
    sensitive_data = {k: v for k, v in sensitive_data.items() if v is not None}
    
    if sensitive_data:
        secure_config.save_secure_config(sensitive_data)
        print("✅ Secure configuration setup complete!")
    else:
        print("⚠️  No sensitive data found to encrypt")

if __name__ == "__main__":
    setup_secure_config()
