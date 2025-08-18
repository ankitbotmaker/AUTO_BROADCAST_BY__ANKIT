import telebot
from telebot import types
from pymongo import MongoClient
import threading
import time

# Bot token
BOT_TOKEN = "7769199668:AAGsMQ6BzCPGu_ONdgnb7QEURkbIb80uyUY"
bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB setup
MONGO_URL = "mongodb+srv://rowojo2049:bga4FhmFXj2GTM5B@cluster0.ggmw5h8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URL)
db = client["broadcast_bot"]
channels_col = db["channels"]

OWNER_ID = 7792539085  # sirf owner control karega

# Track states
broadcast_state = {}
active_reposts = {}  # {chat_id: {"stop": bool}}


# 🔁 Background repost
def auto_repost(chat_id, message, repost_time, delete_time, stop_flag):
    while not stop_flag["stop"]:
        time.sleep(repost_time * 60)
        if stop_flag["stop"]:
            break
        for ch in channels_col.find():
            try:
                sent = None
                if message.content_type == "text":
                    sent = bot.send_message(ch["channel_id"], message.text)
                elif message.content_type == "photo":
                    sent = bot.send_photo(ch["channel_id"], message.photo[-1].file_id, caption=message.caption)
                elif message.content_type == "video":
                    sent = bot.send_video(ch["channel_id"], message.video.file_id, caption=message.caption)
                else:
                    sent = bot.forward_message(ch["channel_id"], message.chat.id, message.message_id)

                if delete_time:
                    threading.Thread(
                        target=auto_delete, args=(ch["channel_id"], sent.message_id, delete_time)
                    ).start()
            except Exception as e:
                print(f"❌ Repost failed for {ch['channel_id']} -> {e}")


# 🗑 Auto delete
def auto_delete(chat_id, msg_id, delete_time):
    time.sleep(delete_time * 60)
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception as e:
        print(f"❌ Delete failed for {chat_id} -> {e}")


# 🚀 Start
@bot.message_handler(commands=["start"])
def start_cmd(message):
    if message.chat.id == OWNER_ID:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"),
            types.InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
        )
        markup.add(
            types.InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel"),
            types.InlineKeyboardButton("📋 Show Channels", callback_data="show_channels"),
        )
        markup.add(
            types.InlineKeyboardButton("🗑 Clear All", callback_data="clear_channels"),
            types.InlineKeyboardButton("📊 Stats", callback_data="stats"),
        )
        markup.add(
            types.InlineKeyboardButton("⏹ Stop Repost", callback_data="stop_repost"),
        )

        bot.send_photo(
            message.chat.id,
            "https://i.ibb.co/GQrGd0MV/a101f4b2bfa4.jpg",
            caption="👋 Welcome to **Broadcast Bot Panel!**\n\nChoose an option below:",
            reply_markup=markup,
            parse_mode="Markdown",
        )
    else:
        bot.send_message(message.chat.id, "🚫 You are not authorized to use this bot.")


# 🎛 Button handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    global broadcast_state, active_reposts
    if call.message.chat.id != OWNER_ID:
        return

    state = broadcast_state.get(call.message.chat.id, {})

    if call.data == "broadcast":
        broadcast_state[call.message.chat.id] = {"step": "waiting_msg"}
        bot.send_message(call.message.chat.id, "📢 Send the message you want to broadcast:")

    elif call.data == "add_channel":
        bot.send_message(
            call.message.chat.id,
            "➕ Send me channel ID (starts with -100) or forward any message from that channel.",
        )

    elif call.data == "remove_channel":
        bot.send_message(call.message.chat.id, "➖ Send me channel ID to remove.")

    elif call.data == "show_channels":
        channels = [str(ch["channel_id"]) for ch in channels_col.find()]
        if channels:
            bot.send_message(call.message.chat.id, "📋 Saved Channels:\n" + "\n".join(channels))
        else:
            bot.send_message(call.message.chat.id, "⚠️ No channels saved.")

    elif call.data == "clear_channels":
        channels_col.delete_many({})
        bot.send_message(call.message.chat.id, "🗑 All channels cleared.")

    elif call.data == "stats":
        total = channels_col.count_documents({})
        bot.send_message(call.message.chat.id, f"📊 Stats:\nTotal Channels: {total}")

    elif call.data == "stop_repost":
        stop_repost(call.message.chat.id)

    # ✅ Repost / Delete flow handle
    elif call.data in ["repost_yes", "repost_no", "delete_yes", "delete_no"]:
        if call.data == "repost_yes":
            state["step"] = "ask_repost_time"
            bot.send_message(call.message.chat.id, "⏱ Enter repost time in minutes:")
        elif call.data == "repost_no":
            state["repost_time"] = None
            state["step"] = "ask_autodelete"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Yes", callback_data="delete_yes"),
                types.InlineKeyboardButton("❌ No", callback_data="delete_no"),
            )
            bot.send_message(call.message.chat.id, "🗑 Do you want Auto Delete for this message?", reply_markup=markup)

        elif call.data == "delete_yes":
            state["step"] = "ask_autodelete_time"
            bot.send_message(call.message.chat.id, "⏱ After how many minutes should the message auto-delete?")
        elif call.data == "delete_no":
            state["delete_time"] = None
            finish_broadcast(call.message.chat.id)

        broadcast_state[call.message.chat.id] = state


# 📩 Handle messages
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global broadcast_state
    if message.chat.id != OWNER_ID:
        return

    state = broadcast_state.get(message.chat.id)

    # Step 1: waiting broadcast msg
    if state and state.get("step") == "waiting_msg":
        state["message"] = message
        state["step"] = "ask_repost"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Yes", callback_data="repost_yes"),
            types.InlineKeyboardButton("❌ No", callback_data="repost_no"),
        )
        bot.send_message(message.chat.id, "♻️ Do you want to Auto Repost this?", reply_markup=markup)
        return

    # Step 2: ask repost time
    if state and state.get("step") == "ask_repost_time":
        try:
            minutes = int(message.text.strip())
            state["repost_time"] = minutes
            state["step"] = "ask_autodelete"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Yes", callback_data="delete_yes"),
                types.InlineKeyboardButton("❌ No", callback_data="delete_no"),
            )
            bot.send_message(message.chat.id, "🗑 Do you want Auto Delete for this message?", reply_markup=markup)
        except:
            bot.send_message(message.chat.id, "⚠️ Please enter a valid number (minutes).")
        return

    # Step 3: ask auto delete time
    if state and state.get("step") == "ask_autodelete_time":
        try:
            minutes = int(message.text.strip())
            state["delete_time"] = minutes
            finish_broadcast(message.chat.id)
        except:
            bot.send_message(message.chat.id, "⚠️ Please enter a valid number (minutes).")
        return

    # Add/remove channels manually
    if message.text and message.text.startswith("-100"):
        ch_id = int(message.text.strip())
        if channels_col.find_one({"channel_id": ch_id}):
            channels_col.delete_one({"channel_id": ch_id})
            bot.send_message(message.chat.id, f"➖ Removed channel {ch_id}")
        else:
            channels_col.insert_one({"channel_id": ch_id})
            bot.send_message(message.chat.id, f"✅ Added channel {ch_id}")


# ✅ Final broadcast
def finish_broadcast(chat_id):
    global active_reposts
    state = broadcast_state.get(chat_id)
    if not state:
        return

    message = state["message"]
    repost_time = state.get("repost_time")
    delete_time = state.get("delete_time")

    sent_count = 0
    failed_count = 0

    for ch in channels_col.find():
        try:
            sent = None
            if message.content_type == "text":
                sent = bot.send_message(ch["channel_id"], message.text)
            elif message.content_type == "photo":
                sent = bot.send_photo(ch["channel_id"], message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == "video":
                sent = bot.send_video(ch["channel_id"], message.video.file_id, caption=message.caption)
            else:
                sent = bot.forward_message(ch["channel_id"], message.chat.id, message.message_id)

            sent_count += 1

            # Auto delete
            if delete_time:
                threading.Thread(
                    target=auto_delete, args=(ch["channel_id"], sent.message_id, delete_time)
                ).start()

        except Exception as e:
            failed_count += 1
            print(f"❌ Failed in {ch['channel_id']} -> {e}")

    bot.send_message(chat_id, f"✅ Broadcast Done!\nSent: {sent_count} | Failed: {failed_count}")

    # Auto repost
    if repost_time:
        bot.send_message(
            chat_id,
            f"♻️ Auto Repost scheduled every {repost_time} minutes.\nUse ⏹ Stop Repost button to cancel.",
        )
        stop_flag = {"stop": False}
        active_reposts[chat_id] = stop_flag
        threading.Thread(
            target=auto_repost, args=(chat_id, message, repost_time, delete_time, stop_flag)
        ).start()

    broadcast_state.pop(chat_id, None)


# ⏹ Stop repost
def stop_repost(chat_id):
    global active_reposts
    if chat_id in active_reposts:
        active_reposts[chat_id]["stop"] = True
        del active_reposts[chat_id]
        bot.send_message(chat_id, "⏹ Auto Repost stopped.")
    else:
        bot.send_message(chat_id, "⚠️ No active repost running.")


print("🤖 Bot started...")
bot.infinity_polling()
