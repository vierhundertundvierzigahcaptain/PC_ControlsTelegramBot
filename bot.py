import telebot
from telebot import types

import config
import remote

bot = telebot.TeleBot(config.TOKEN)


def authorized_only(handler):
    def wrapper(event):
        chat = event.chat if hasattr(event, "chat") else event.message.chat
        if chat.id != config.ALLOWED_USER_ID:
            bot.send_message(chat.id, f"Access denied. Your ID: {chat.id}")
            return
        return handler(event)

    return wrapper


def send_remote(chat_id):
    if not remote.public_url:
        bot.send_message(chat_id, "Remote tunnel is not available")
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Open remote", web_app=types.WebAppInfo(url=remote.public_url))
    )
    bot.send_message(chat_id, "Remote control:", reply_markup=markup)


@bot.message_handler(commands=["start"])
@authorized_only
def start(message):
    send_remote(message.chat.id)


if __name__ == "__main__":
    try:
        remote.start(config.REMOTE_PORT, config.NGROK_AUTHTOKEN)
    except Exception as error:
        print(f"Remote unavailable: {error}")
    bot.infinity_polling()
