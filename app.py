import os
from flask import Flask, request
from dotenv import load_dotenv
load_dotenv()

from bot import bot

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Ankit Broadcast Bot is running!"

@app.route(f'/{os.environ.get("BOT_TOKEN")}', methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([update])
    return 'OK'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
