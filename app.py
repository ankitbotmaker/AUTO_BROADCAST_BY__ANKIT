import os
import logging
from flask import Flask, request

# Set up environment variables
from dotenv import load_dotenv
load_dotenv()

# Import bot after environment setup
from bot import bot, logger

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Ankit Broadcast Bot is running!"

@app.route(f'/{os.environ.get("BOT_TOKEN")}', methods=['POST'])
def webhook():
    """Handle webhook requests from Telegram"""
    try:
        update = request.get_json()
        bot.process_new_updates([update])
        return 'OK'
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    # Set up webhook for Heroku
    try:
        bot.remove_webhook()
        webhook_url = f"https://ankitbb.herokuapp.com/{os.environ.get('BOT_TOKEN')}"
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook set successfully: {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
    
    app.run(host='0.0.0.0', port=port)
