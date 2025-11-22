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

# Синхронная установка вебхука
def setup_webhook():
    try:
        RENDER_URL = "https://telegram-bot-kie.onrender.com"
        webhook_url = f"{RENDER_URL}/webhook"
        
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

# Генерация изображения через KIE API
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
        
        logger.info(f"🔄 Отправка запроса к KIE API: {prompt}")
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("images"):
                image_url = result["images"][0]
                logger.info(f"✅ Изображение сгенерировано: {image_url}")
                return image_url
            else:
                logger.error(f"❌ Нет images в ответе: {result}")
                return None
        else:
            logger.error(f"❌ Ошибка KIE API: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        return None

# Обработка сообщений
def process_message(chat_id, text):
    try:
        if text == '/start':
            message_text = "🎨 Бот для генерации изображений!\n\n/generate - создать изображение\n/balance - проверить баланс\n/help - помощь"
            send_telegram_message(chat_id, message_text)
            
        elif text == '/help':
            message_text = "📖 Отправь описание картинки или используй /generate\n\nПример: 'Кот в космосе с ракетой'"
            send_telegram_message(chat_id, message_text)
            
        elif text == '/balance':
            message_text = "💰 Баланс: 10 тестовых кредитов\n\n1 генерация = 1 кредит"
            send_telegram_message(chat_id, message_text)
            
        elif text == '/generate':
            message_text = "📝 Напиши описание картинки...\n\nНапример: 'Кот в космосе' или 'Город будущего'"
            send_telegram_message(chat_id, message_text)
            
        else:
            # Генерация изображения
            send_telegram_message(chat_id, f"🔄 Генерирую: '{text}'...")
            
            image_url = generate_image(text)
            
            if image_url:
                # Отправляем изображение
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    json={
                        "chat_id": chat_id,
                        "photo": image_url,
                        "caption": f"🎨 Сгенерировано: '{text}'"
                    }
                )
                if response.status_code == 200:
                    logger.info(f"✅ Изображение отправлено")
                else:
                    send_telegram_message(chat_id, "❌ Ошибка отправки изображения")
            else:
                send_telegram_message(chat_id, "❌ Ошибка генерации. Попробуй другой запрос.")
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        send_telegram_message(chat_id, "❌ Произошла ошибка")

# Вспомогательная функция для отправки сообщений
def send_telegram_message(chat_id, text):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            }
        )
        if response.status_code != 200:
            logger.error(f"❌ Ошибка отправки сообщения: {response.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")

@app.route('/')
def home():
    return "Бот работает! ✅ Генерация активна"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        try:
            update_data = request.get_json()
            
            if 'message' in update_data:
                chat_id = update_data['message']['chat']['id']
                text = update_data['message']['text']
                logger.info(f"💬 Сообщение: {text} от {chat_id}")
                
                process_message(chat_id, text)
            
            return 'ok'
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return 'error'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
