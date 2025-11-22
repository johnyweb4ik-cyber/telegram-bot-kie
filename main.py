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
        # Пробуем разные endpoints KIE API
        endpoints = [
            "https://api.kie.ai/v1/images/generations",  # Возможный правильный endpoint
            "https://api.kie.ai/v1/generate/image",      # Альтернативный вариант
            "https://api.kie.ai/v1/image/generate"       # Еще один вариант
        ]
        
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
        
        for endpoint in endpoints:
            logger.info(f"🔄 Пробуем endpoint: {endpoint}")
            
            response = requests.post(endpoint, json=data, headers=headers, timeout=60)
            logger.info(f"📡 Ответ {endpoint}: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"📦 Успешный ответ: {result}")
                
                # Пробуем разные форматы ответа
                if result.get("images"):
                    return result["images"][0]
                elif result.get("data") and result["data"].get("url"):
                    return result["data"]["url"]
                elif result.get("url"):
                    return result["url"]
                else:
                    logger.info(f"📋 Структура ответа: {result}")
                    
            elif response.status_code != 404:
                logger.info(f"📋 Ответ при ошибке: {response.text}")
        
        return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка KIE: {e}")
        return None

def process_message(chat_id, text):
    logger.info(f"🔧 Обработка: {text}")
    
    try:
        if text == '/start':
            send_message(chat_id, "🎨 Бот для генерации изображений! Напиши описание картинки")
            return
            
        if text == '/balance':
            send_message(chat_id, "💰 Баланс: 10 кредитов")  
            return
            
        if text in ['/help', '/generate']:
            send_message(chat_id, "📝 Пример: 'Кот в космосе с ракетой'")
            return
        
        # Генерация
        logger.info(f"🎨 Генерация: {text}")
        send_message(chat_id, f"🔄 Генерирую: '{text}'...")
        
        image_url = generate_image(text)
        
        if image_url:
            logger.info(f"✅ Успех! Отправляем фото...")
            send_telegram_photo(chat_id, image_url, text)
        else:
            logger.error("❌ Генерация не удалась")
            send_message(chat_id, "❌ Ошибка: проверь API ключ KIE или попробуй позже")
            
    except Exception as e:
        logger.error(f"💥 Ошибка: {e}")
        send_message(chat_id, "❌ Произошла ошибка")

def send_telegram_photo(chat_id, image_url, prompt):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id": chat_id,
                "photo": image_url,
                "caption": f"🎨 Сгенерировано: '{prompt}'"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Фото отправлено")
        else:
            logger.error(f"❌ Ошибка фото: {response.text}")
            send_message(chat_id, f"✅ Сгенерировано! URL: {image_url}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки фото: {e}")
        send_message(chat_id, f"✅ Сгенерировано! URL: {image_url}")

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
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            if 'message' in data:
                chat_id = data['message']['chat']['id']
                text = data['message']['text']
                logger.info(f"💬 Сообщение: {text}")
                
                process_message(chat_id, text)
            
            return 'ok'
            
        except Exception as e:
            logger.error(f"❌ Ошибка webhook: {e}")
            return 'error'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
