import os
import logging
import requests
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

logger.info(f"BOT_TOKEN exists: {BOT_TOKEN is not None}")
logger.info(f"KIE_API_KEY exists: {KIE_API_KEY is not None}")

def setup_webhook():
    try:
        RENDER_URL = "https://telegram-bot-kie.onrender.com"
        webhook_url = f"{RENDER_URL}/webhook"
        
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Webhook установлен")
        else:
            logger.error(f"❌ Ошибка вебхука: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка вебхука: {e}")

setup_webhook()

def generate_image(prompt):
    try:
        url = "https://api.kie.ai/v1/image/generation"
        headers = {
            "Authorization": f"Bearer {KIE_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "nano-banana", 
            "prompt": prompt,
            "width": 1024,
            "height": 1024
        }
        
        logger.info(f"🔄 Отправка в KIE API...")
        response = requests.post(url, json=data, headers=headers, timeout=60)
        logger.info(f"📡 KIE ответ: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("images"):
                return result["images"][0]
        return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка KIE: {e}")
        return None

def process_message(chat_id, text):
    logger.info(f"🔧 Начало обработки: {text}")
    
    try:
        # Простые команды
        if text == '/start':
            send_message(chat_id, "🎨 Бот для генерации изображений! Просто напиши описание картинки")
            return
            
        if text == '/balance':
            send_message(chat_id, "💰 Баланс: 10 кредитов")  
            return
            
        if text in ['/help', '/generate']:
            send_message(chat_id, "📝 Напиши описание картинки...")
            return
        
        # ВСЕ остальное - пытаемся генерировать
        logger.info(f"🎨 Запуск генерации для: {text}")
        send_message(chat_id, f"🔄 Генерирую: '{text}'...")
        
        image_url = generate_image(text)
        
        if image_url:
            logger.info(f"✅ Успех! URL: {image_url}")
            # Пытаемся отправить фото
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": f"🎨 Сгенерировано: '{text}'"
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Ошибка отправки фото: {response.text}")
                send_message(chat_id, "✅ Сгенерировано! Но ошибка отправки.")
        else:
            logger.error("❌ Генерация не удалась")
            send_message(chat_id, "❌ Ошибка генерации. Проверь API ключ KIE.")
            
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        send_message(chat_id, "❌ Произошла ошибка")

def send_message(chat_id, text):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text}
        )
        if response.status_code != 200:
            logger.error(f"❌ Ошибка сообщения: {response.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")

@app.route('/')
def home():
    return "Бот работает! ✅"

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("📨 Запрос от Telegram")
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            logger.info(f"📦 Данные получены")
            
            if 'message' in data:
                chat_id = data['message']['chat']['id']
                text = data['message']['text']
                logger.info(f"💬 Текст: {text}")
                
                process_message(chat_id, text)
            
            return 'ok'
            
        except Exception as e:
            logger.error(f"❌ Ошибка webhook: {e}")
            return 'error'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
