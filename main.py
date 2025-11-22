import os
import logging
import requests
import base64
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

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
        # Правильный endpoint для KIE API
        url = "https://api.kie.ai/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {KIE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Данные для генерации изображения через chat/completions
        data = {
            "model": "nano-banana",  # Или "flux-pro/v1.1" для другого моделя
            "messages": [
                {
                    "role": "user",
                    "content": f"Сгенерируй изображение: {prompt}"
                }
            ],
            "max_tokens": 1000
        }
        
        logger.info(f"🔄 Отправка в KIE API chat/completions...")
        response = requests.post(url, json=data, headers=headers, timeout=60)
        logger.info(f"📡 Ответ KIE: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"📦 Структура ответа: {result}")
            
            # Пробуем разные варианты извлечения изображения
            if result.get("choices"):
                content = result["choices"][0].get("message", {}).get("content", "")
                if content and content.startswith("http"):
                    return content
                    
            # Если нет URL в content, возвращаем информацию для отладки
            return f"Ответ получен: {result}"
        else:
            logger.error(f"❌ Ошибка KIE API: {response.status_code} - {response.text}")
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
        
        result = generate_image(text)
        
        if result:
            logger.info(f"✅ Успех! Результат: {result}")
            send_message(chat_id, f"🎨 Результат: {result}")
        else:
            logger.error("❌ Генерация не удалась")
            send_message(chat_id, "❌ Ошибка генерации")
            
    except Exception as e:
        logger.error(f"💥 Ошибка: {e}")
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
