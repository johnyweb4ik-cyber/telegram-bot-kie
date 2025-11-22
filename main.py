import os
import logging
from flask import Flask, request
from telegram import Bot, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

bot = Bot(token=BOT_TOKEN)

# Флаг для отслеживания установки вебхука
webhook_set = False

@app.route('/')
def home():
    global webhook_set
    RENDER_URL = "https://telegram-bot-kie.onrender.com"
    webhook_url = f"{RENDER_URL}/webhook"
    
    if not webhook_set:
        try:
            bot.set_webhook(webhook_url)
            logger.info(f"✅ Webhook установлен: {webhook_url}")
            webhook_set = True
            return "Бот работает! ✅ Вебхук установлен"
        except Exception as e:
            return f"Бот работает! ❌ Ошибка вебхука: {e}"
    else:
        return "Бот работает! ✅ Вебхук уже установлен"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = Update.de_json(request.get_json(), bot)
        
        if update.message:
            chat_id = update.message.chat.id
            text = update.message.text
            
            if text == '/start':
                bot.send_message(chat_id, "Привет! Я бот для генерации изображений. Отправь мне описание картинки.")
            else:
                bot.send_message(chat_id, f"Получил: '{text}'. Режим тестирования - скоро будет генерация!")
    
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
