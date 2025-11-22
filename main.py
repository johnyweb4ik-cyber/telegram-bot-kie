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

# Устанавливаем вебхук при первом запросе
@app.before_first_request
def setup_webhook():
    RENDER_URL = "https://telegram-bot-kie.onrender.com"
    webhook_url = f"{RENDER_URL}/webhook"
    try:
        bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Ошибка вебхука: {e}")

@app.route('/')
def home():
    # При заходе на главную страницу устанавливаем вебхук
    RENDER_URL = "https://telegram-bot-kie.onrender.com"
    webhook_url = f"{RENDER_URL}/webhook"
    try:
        bot.set_webhook(webhook_url)
        return "Бот работает! ✅ Вебхук установлен"
    except Exception as e:
        return f"Бот работает! ❌ Ошибка вебхука: {e}"

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
