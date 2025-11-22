import os
import logging
import requests
from flask import Flask, request
from telegram import Bot, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

logger.info(f"BOT_TOKEN exists: {BOT_TOKEN is not None}")
logger.info(f"KIE_API_KEY exists: {KIE_API_KEY is not None}")

bot = Bot(token=BOT_TOKEN)

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
            return "Бот работает! ✅ Вебхук активен"
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return f"Бот работает! ❌ Ошибка: {e}"
    else:
        return "Бот работает! ✅ Вебхук активен"

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("📨 Получен запрос от Telegram")
    
    if request.method == 'POST':
        try:
            update_data = request.get_json()
            logger.info(f"📦 Данные от Telegram: {update_data}")
            
            update = Update.de_json(update_data, bot)
            
            if update.message:
                chat_id = update.message.chat.id
                text = update.message.text
                logger.info(f"💬 Сообщение: {text} от {chat_id}")
                
                if text == '/start':
                    logger.info("🔄 Обработка /start")
                    bot.send_message(chat_id, "🎨 Бот работает! Команды активны")
                else:
                    logger.info(f"🔄 Обработка текста: {text}")
                    bot.send_message(chat_id, f"📝 Получил: {text}")
            
            return 'ok'
            
        except Exception as e:
            logger.error(f"❌ Ошибка в webhook: {e}")
            return 'error'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
