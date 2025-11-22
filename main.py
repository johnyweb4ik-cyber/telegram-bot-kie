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

# Создаем бота
bot = Bot(token=BOT_TOKEN)

# Синхронная установка вебхука
def setup_webhook():
    try:
        RENDER_URL = "https://telegram-bot-kie.onrender.com"
        webhook_url = f"{RENDER_URL}/webhook"
        
        # Используем низкоуровневый HTTP запрос для установки вебхука
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Webhook установлен: {webhook_url}")
        else:
            logger.error(f"❌ Ошибка вебхука: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка вебхука: {e}")

# Устанавливаем вебхук при старте
setup_webhook()

# Синхронная обработка сообщений
def process_message(chat_id, text):
    try:
        if text == '/start':
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "🎨 Бот работает! Команды активны\n\n/generate - создать изображение\n/balance - проверить баланс\n/help - помощь"
                }
            )
        elif text == '/help':
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id, 
                    "text": "📖 Просто отправь описание картинки или используй /generate"
                }
            )
        elif text == '/balance':
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "💰 Баланс: 10 тестовых кредитов"
                }
            )
        elif text == '/generate':
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                json={
                    "chat_id": chat_id,
                    "text": "📝 Напиши описание картинки...\n\nНапример: 'Кот в космосе' или 'Город будущего'"
                }
            )
        else:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"🎨 Скоро я сгенерирую: '{text}'\n\nСейчас в разработке..."
                }
            )
            
        if response.status_code != 200:
            logger.error(f"❌ Ошибка отправки: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")

@app.route('/')
def home():
    return "Бот работает! ✅ Вебхук настроен"

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("📨 Получен запрос от Telegram")
    
    if request.method == 'POST':
        try:
            update_data = request.get_json()
            
            if 'message' in update_data:
                chat_id = update_data['message']['chat']['id']
                text = update_data['message']['text']
                logger.info(f"💬 Сообщение: {text} от {chat_id}")
                
                # Обрабатываем сообщение
                process_message(chat_id, text)
            
            return 'ok'
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return 'error'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
