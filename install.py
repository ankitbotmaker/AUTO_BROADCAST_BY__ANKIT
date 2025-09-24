#!/usr/bin/env python3
"""
Advanced Telegram Broadcast Bot - Installation Script
Helps users set up the bot with proper configuration
"""

import os
import sys
import subprocess
from pathlib import Path

def print_banner():
    """Print installation banner"""
    print("""
🚀 Advanced Telegram Broadcast Bot v3.0 - Installation
====================================================

This script will help you set up the bot with all required dependencies
and configuration files.

Features:
• 📢 Multi-Channel Broadcasting  
• ⚡ Auto Repost & Delete
• 📊 Advanced Analytics
• 🔗 Auto Link Detection
• ⏰ Scheduled Broadcasts
• 🎨 Message Templates
• 📈 Real-time Analytics

ALL FEATURES ARE FREE! 🎉
""")

def check_python_version():
    """Check if Python version is compatible"""
    print("🔍 Checking Python version...")
    
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ is required!")
        print(f"   Current version: {sys.version}")
        print("   Please upgrade Python and try again.")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} is compatible")
    return True

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    
    try:
        # Check if requirements.txt exists
        if not Path("requirements.txt").exists():
            print("❌ requirements.txt not found!")
            return False
        
        # Install requirements
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully!")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def create_env_file():
    """Create .env file from template"""
    print("\n📝 Setting up environment configuration...")
    
    env_file = Path(".env")
    env_example = Path("env_example.txt")
    
    if env_file.exists():
        response = input("⚠️  .env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("📄 Keeping existing .env file")
            return True
    
    if not env_example.exists():
        print("❌ env_example.txt not found!")
        return False
    
    # Copy template to .env
    try:
        with open(env_example, 'r', encoding='utf-8') as f:
            content = f.read()
        
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ .env file created from template")
        return True
    
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")
        return False

def get_user_config():
    """Get configuration from user"""
    print("\n⚙️  Bot Configuration")
    print("=" * 50)
    
    config = {}
    
    # Bot Token
    print("\n1. Bot Token:")
    print("   • Create a bot with @BotFather on Telegram")
    print("   • Send /newbot and follow instructions")
    print("   • Copy the token you receive")
    
    while True:
        token = input("\n🤖 Enter your bot token: ").strip()
        if token and len(token) > 10 and ':' in token:
            config['BOT_TOKEN'] = token
            break
        print("❌ Invalid token format. Please try again.")
    
    # MongoDB URL
    print("\n2. MongoDB Database:")
    print("   • Option 1: Use MongoDB Atlas (free cloud database)")
    print("   • Option 2: Use local MongoDB installation")
    print("   • Get connection string from your MongoDB provider")
    
    while True:
        mongo_url = input("\n🗄️  Enter MongoDB URL: ").strip()
        if mongo_url and ('mongodb' in mongo_url.lower()):
            config['MONGO_URL'] = mongo_url
            break
        print("❌ Invalid MongoDB URL. Please try again.")
    
    # Admin IDs
    print("\n3. Admin User IDs:")
    print("   • Get your Telegram user ID from @userinfobot")
    print("   • You can add multiple IDs separated by commas")
    
    while True:
        admin_ids = input("\n👨‍💼 Enter admin user ID(s): ").strip()
        if admin_ids and admin_ids.replace(',', '').replace(' ', '').isdigit():
            config['ADMIN_IDS'] = admin_ids
            config['OWNER_ID'] = admin_ids.split(',')[0].strip()
            break
        print("❌ Invalid user ID format. Please enter numbers only.")
    
    return config

def update_env_file(config):
    """Update .env file with user configuration"""
    print("\n💾 Updating configuration file...")
    
    try:
        env_file = Path(".env")
        
        # Read current content
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace placeholders with actual values
        replacements = {
            'your_bot_token_here': config['BOT_TOKEN'],
            'your_mongodb_connection_string': config['MONGO_URL'],
            'your_admin_user_id_here': config['ADMIN_IDS'],
            'your_owner_user_id_here': config['OWNER_ID']
        }
        
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        
        # Write updated content
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Configuration file updated successfully!")
        return True
    
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False

def test_configuration():
    """Test bot configuration"""
    print("\n🧪 Testing configuration...")
    
    try:
        # Try to import and validate config
        from config import validate_config
        validate_config()
        print("✅ Configuration is valid!")
        return True
    
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("\n💡 Please check your .env file and fix any issues.")
        return False

def show_next_steps():
    """Show next steps to user"""
    print("""
🎉 Installation Complete!

🚀 Next Steps:
1. Start the bot:
   python bot.py

2. Send /start to your bot in Telegram

3. Add channels using /add command

4. Start broadcasting! 📢

📚 Documentation:
• Check README.md for detailed instructions
• All features are FREE - no premium required!
• Support: Create an issue on GitHub

💡 Tips:
• Make sure your bot is admin in channels you want to broadcast to
• Use /id command to get channel IDs
• Monitor /admin panel for system status

Happy Broadcasting! 🚀
""")

def main():
    """Main installation function"""
    print_banner()
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Installation failed at dependency installation step.")
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        print("\n❌ Installation failed at environment setup step.")
        sys.exit(1)
    
    # Get user configuration
    config = get_user_config()
    
    # Update .env file
    if not update_env_file(config):
        print("\n❌ Installation failed at configuration update step.")
        sys.exit(1)
    
    # Test configuration
    if not test_configuration():
        print("\n⚠️  Configuration test failed, but installation is complete.")
        print("   Please review your .env file and fix any issues.")
    
    # Show next steps
    show_next_steps()

if __name__ == "__main__":
    main()
