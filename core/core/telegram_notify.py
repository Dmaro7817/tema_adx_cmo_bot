import telegram

def send_telegram_message(token, chat_id, text):
    bot = telegram.Bot(token=token)
    bot.send_message(chat_id=chat_id, text=text)
