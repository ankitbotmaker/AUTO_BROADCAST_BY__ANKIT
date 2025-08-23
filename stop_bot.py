#!/usr/bin/env python3
"""
Force Stop Bot Script
This script will force stop all bot instances and clear webhooks
"""

import requests
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import config
try:
    from config import BOT_TOKEN
except ImportError:
    print("❌ Config file not found!")
    exit(1)

def force_stop_bot():
    """Force stop all bot instances and clear webhooks"""
    print("🛑 Force stopping all bot instances...")
    
    # Multiple attempts to delete webhook
    for attempt in range(10):
        try:
            # Delete webhook
            delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
            response = requests.post(delete_url, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"✅ Webhook deletion attempt {attempt + 1} successful")
                else:
                    print(f"⚠️ Webhook deletion attempt {attempt + 1} failed: {result}")
            else:
                print(f"⚠️ Webhook deletion attempt {attempt + 1} failed with status {response.status_code}")
            
            # Get updates to clear any pending updates
            get_updates_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            updates_response = requests.get(get_updates_url, timeout=10)
            
            if updates_response.status_code == 200:
                updates_result = updates_response.json()
                if updates_result.get("ok"):
                    updates = updates_result.get("result", [])
                    print(f"📋 Cleared {len(updates)} pending updates")
            
            time.sleep(2)  # Wait between attempts
            
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    
    print("✅ Force stop completed!")
    print("🔄 Now you can run the bot locally without conflicts")

if __name__ == "__main__":
    force_stop_bot()
