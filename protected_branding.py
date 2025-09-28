"""
Protected Ankit Branding System
Encoded branding that cannot be easily edited by users
"""

import base64
import zlib
import json

class ProtectedBranding:
    def __init__(self):
        # Encoded branding data - cannot be easily edited
        self._encoded_data = "eJw9zjEPgjAQBeC/cungZACN0YQN42ri4MhS4AqNLUfaK0aN/902GNZ33728j+hwRkMTOlGCqMaHZrEF0WseQpOigXnyZZ4vSdaSzWVSDbGVj/gWNWs2mPDNkULvNY3SwJkYLmt7ZH7CVkuj35KjSP6OBnsnbbIeNlAFJrtco1dEvOy6yg7hGRdAHfan46EOCgsFzQvWxTM6/2/dZUVWiO8PL3ZIpQ=="
        self._branding = self._decode_branding()
    
    def _decode_branding(self):
        """Decode branding data"""
        try:
            compressed = base64.b64decode(self._encoded_data.encode())
            json_data = zlib.decompress(compressed).decode()
            return json.loads(json_data)
        except:
            # Fallback branding
            return {
                "developer": "Ankit",
                "github": "https://github.com/ankitbotmaker",
                "title": "Professional Bot Developer",
                "specialization": "Telegram Bots & Automation",
                "footer": "Made with ❤️ by Ankit",
                "version": "1.0.0"
            }
    
    def get_developer_name(self):
        """Get developer name"""
        return self._branding.get("developer", "Ankit")
    
    def get_github_url(self):
        """Get GitHub URL"""
        return self._branding.get("github", "https://github.com/ankitbotmaker")
    
    def get_title(self):
        """Get developer title"""
        return self._branding.get("title", "Professional Bot Developer")
    
    def get_specialization(self):
        """Get specialization"""
        return self._branding.get("specialization", "Telegram Bots & Automation")
    
    def get_footer(self):
        """Get footer text"""
        return self._branding.get("footer", "Made with ❤️ by Ankit")
    
    def get_version(self):
        """Get version"""
        return self._branding.get("version", "1.0.0")
    
    def get_welcome_branding(self):
        """Get welcome message branding"""
        return f"""
<b>👨‍💻 Developed by <a href="{self.get_github_url()}">{self.get_developer_name()}</a></b>
<blockquote>
🚀 {self.get_title()}
💼 Specialized in {self.get_specialization()}
</blockquote>"""
    
    def get_footer_branding(self):
        """Get footer branding"""
        return f"""
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>
<b>🔥 {self.get_footer()}</b>"""
    
    def get_about_developer(self):
        """Get about developer section"""
        return f"""
## 👨‍💻 About the Developer

**{self.get_developer_name()}** - {self.get_title()}
- 🚀 **Specialization**: {self.get_specialization()}
- 💼 **Experience**: Advanced bot development with modern features
- 🔧 **Skills**: Python, Telegram API, MongoDB, Encryption, Deployment
- 🌟 **Mission**: Creating powerful, user-friendly automation solutions

### **Connect with {self.get_developer_name()}:**
- **GitHub**: [@{self.get_developer_name().lower()}botmaker]({self.get_github_url()})
- **Portfolio**: Professional bot development services
- **Support**: Available for custom bot development
"""

# Global protected branding instance
protected_branding = ProtectedBranding()
