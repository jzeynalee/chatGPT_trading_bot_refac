from telegram import Bot

class TelegramNotifier:
    '''
    telegramAPI   = 'https://api.telegram.org/bot'
    scalperSignalsBot_token = "1985857566:AAHAGuAGm-pVpjFOoxll02D6fSHYb3fQ9MU"
    myFarsiChatId_pub= "@sood_futures"
    myFarsiChatId_prv = "-1001578355499"
    '''
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    def send_message(self, text):
        try:
            self.bot.send_message(chat_id=self.chat_id, text=text)
        except Exception as e:
            print(f"[Telegram Error] {e}")
