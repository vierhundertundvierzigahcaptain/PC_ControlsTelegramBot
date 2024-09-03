import functional
import telebot
import config

from telebot import types

bot = telebot.TeleBot(config.TOKEN)


def create_keyboard(buttons):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*buttons)
    return markup


def create_main_keyboard():
    buttons = [
        types.KeyboardButton("PC controls"),
        types.KeyboardButton("Sound controls"),
    ]
    return create_keyboard(buttons)


def create_pc_controls_keyboard():
    buttons = [
        types.KeyboardButton("Shutdown"),
        types.KeyboardButton("Sleep mode"),
        types.KeyboardButton("Restart"),
        types.KeyboardButton("Logoff"),
        types.KeyboardButton("Back"),
    ]
    return create_keyboard(buttons)


def create_sound_keyboard():
    buttons = [
        types.KeyboardButton("-2%"),
        types.KeyboardButton("-10%"),
        types.KeyboardButton("+2%"),
        types.KeyboardButton("+10%"),
        types.KeyboardButton("Mute"),
        types.KeyboardButton("Back"),
    ]
    return create_keyboard(buttons)


def handle_command(message, command_text, action, response_text):
    if message.text == command_text:
        action()
        bot.send_message(message.chat.id, response_text)


@bot.message_handler(commands=['start'])
def start(message):
    main_markup = create_main_keyboard()
    bot.send_message(message.chat.id, 'START', reply_markup=main_markup)


@bot.message_handler(content_types=['text'])
def commands(message):
    command_handlers = {
        'Shutdown': (functional.shutdown_pc, 'Shutdown system'),
        'Sleep mode': (functional.sleep_mode_pc, 'Put the system into sleep mode'),
        'Restart': (functional.restart_pc, 'Restart system'),
        'Logoff': (functional.logoff_pc, 'Logoff system'),
        '-2%': (functional.reduce_volume_by_2, 'Sound reduced by 2%'),
        '-10%': (functional.reduce_volume_by_10, 'Sound reduced by 10%'),
        '+2%': (functional.increase_volume_by_2, 'Sound Increased by 2%'),
        '+10%': (functional.increase_volume_by_10, 'Sound Increased by 10%'),
        'Mute': (functional.mute_sound, 'Sound is muted'),
    }

    if message.text == 'PC controls':
        markup = create_pc_controls_keyboard()
        bot.send_message(message.chat.id, 'Choose an option', reply_markup=markup)
    elif message.text == 'Sound controls':
        markup = create_sound_keyboard()
        bot.send_message(message.chat.id, 'Choose an option', reply_markup=markup)
    elif message.text == 'Back':
        markup = create_main_keyboard()
        bot.send_message(message.chat.id, 'Main menu:', reply_markup=markup)
    elif message.text in command_handlers:
        action, response_text = command_handlers[message.text]
        handle_command(message, message.text, action, response_text)
    else:
        markup = create_main_keyboard()
        bot.send_message(message.chat.id, 'Unknown command', reply_markup=markup)


bot.infinity_polling()
