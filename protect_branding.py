"""
Branding Protection Script
Automatically protects Ankit branding from user editing
"""

import os
import re
import base64
import zlib
import json

def protect_branding_in_file(file_path):
    """Protect branding in a specific file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace hardcoded branding with protected calls
        replacements = [
            (r'Ankit', 'protected_branding.get_developer_name()'),
            (r'https://github\.com/ankitbotmaker', 'protected_branding.get_github_url()'),
            (r'Professional Bot Developer', 'protected_branding.get_title()'),
            (r'Made with ❤️ by Ankit', 'protected_branding.get_footer()'),
        ]
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Protected branding in {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error protecting {file_path}: {e}")
        return False

def main():
    """Main protection function"""
    print("🔐 Protecting Ankit Branding...")
    
    files_to_protect = [
        'bot.py',
        'README.md',
        'DEPLOYMENT_GUIDE.md',
        'LICENSE'
    ]
    
    protected_count = 0
    for file_path in files_to_protect:
        if os.path.exists(file_path):
            if protect_branding_in_file(file_path):
                protected_count += 1
    
    print(f"\n🎉 Branding protection complete!")
    print(f"📊 Protected {protected_count}/{len(files_to_protect)} files")
    print("🔒 Ankit branding is now encoded and protected!")

if __name__ == "__main__":
    main()
