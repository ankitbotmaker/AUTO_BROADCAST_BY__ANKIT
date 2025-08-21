import os
import logging
from flask import Flask, request
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
    app.run(host='0.0.0.0', port=port)
