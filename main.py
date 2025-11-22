import os
import logging
import requests
import time
import json
import base64
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = "AIzaSyCJXtPnJsFlEilLgJEZzCqtN3klDZrotWE"  # Твой ключ

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

def generate_image_gemini(prompt):
    """Генерация через Gemini API используя Imagen 3"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:generateContent"
        
        headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': GEMINI_API_KEY
        }
        
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Сгенерируй изображение: {prompt}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "numberOfImages": 1
            }
        }
        
        logger.info(f"🔄 Отправка запроса к Gemini Imagen 3...")
        response = requests.post(url, headers=headers, json=data, timeout=60)
        logger.info(f"📡 Ответ Gemini: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"📦 Ответ получен")
            
            # Парсим ответ чтобы найти URL изображения
            if "candidates" in result and result["candidates"]:
                candidate = result["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inlineData" in part:
                            image_data = part["inlineData"]["data"]
                            # Конвертируем base64 в данные для Telegram
                            return f"data:image/png;base64,{image_data}"
            
            logger.info(f"📋 Полный ответ: {result}")
            return "Изображение сгенерировано, но не найден URL"
            
        else:
            logger.error(f"❌ Ошибка Gemini API: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации через Gemini: {e}")
        return None

def generate_image_gemini_direct(prompt):
    """Альтернативный метод - используем text-to-image напрямую"""
    try:
        # Пробуем другой endpoint для генерации изображений
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:generateContent"
        
        headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': GEMINI_API_KEY
        }
        
        # Более простая структура для генерации изображений
        data = {
            "prompt": prompt,
            "numberOfImages": 1,
            "aspectRatio": "1:1"
        }
        
        logger.info(f"🔄 Прямая генерация изображения...")
        response = requests.post(url, headers=headers, json=data, timeout=60)
        logger.info(f"📡 Ответ: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Изображение сгенерировано")
            
            # Ищем изображение в ответе
            if "images" in result and result["images"]:
                image_url = result["images"][0]
                return image_url
            else:
                logger.info(f"📋 Структура ответа: {result}")
                return "Генерация завершена"
                
        else:
            logger.error(f"❌ Ошибка: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка прямой генерации: {e}")
        return None

def process_message(chat_id, text):
    logger.info(f"🔧 Обработка: {text}")
    
    try:
        if text == '/start':
            send_message(chat_id, 
                "🎨 Бот для генерации изображений!\n\n"
                "✨ Используем Google Gemini API\n"
                "📝 Просто напиши описание картинки\n\n"
                "Команды:\n"
                "/generate - создать изображение\n" 
                "/help - помощь"
            )
            return
            
        if text == '/balance':
            send_message(chat_id, 
                "💰 Используем Google Gemini API\n\n"
                "• Бесплатный лимит: 60 запросов/мин\n"
                "• Качество: высокое\n"
                "• Скорость: быстрая"
            )  
            return
            
        if text in ['/help', '/generate']:
            send_message(chat_id, 
                "📝 Напиши описание картинки\n\n"
                "Примеры:\n"
                "• 'Кот в космосе'\n" 
                "• 'Город будущего'\n"
                "• 'Закат на пляже'\n"
                "• 'Робот читает книгу'"
            )
            return
        
        # Генерация через Gemini API
        logger.info(f"🎨 Генерация: {text}")
        send_message(chat_id, f"🔄 Генерирую: '{text}'...\nИспользую Google Gemini 🚀")
        
        # Пробуем первый метод
        image_data = generate_image_gemini(text)
        
        if image_data:
            if image_data.startswith(('http://', 'https://', 'data:image')):
                logger.info(f"✅ Успех! Отправляем изображение...")
                send_telegram_photo(chat_id, image_data, text)
            else:
                logger.info(f"📋 Результат: {image_data}")
                send_message(chat_id, f"📋 Статус: {image_data}")
        else:
            # Пробуем второй метод
            logger.info("🔄 Пробуем альтернативный метод...")
            image_data = generate_image_gemini_direct(text)
            
            if image_data:
                if image_data.startswith(('http://', 'https://', 'data:image')):
                    send_telegram_photo(chat_id, image_data, text)
                else:
                    send_message(chat_id, f"📋 Результат: {image_data}")
            else:
                logger.error("❌ Оба метода не сработали")
                send_message(chat_id, 
                    "❌ Ошибка генерации\n\n"
                    "Попробуй:\n"
                    "• Другой запрос\n" 
                    "• Подожди немного\n"
                    "• Проверь API ключ"
                )
            
    except Exception as e:
        logger.error(f"💥 Ошибка: {e}")
        send_message(chat_id, "❌ Произошла ошибка")

def send_telegram_photo(chat_id, image_data, prompt):
    """Отправка фото в Telegram"""
    try:
        if image_data.startswith('data:image'):
            # Для base64 данных
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={
                    'chat_id': chat_id,
                    'caption': f"🎨 Gemini API: '{prompt}'"
                },
                files={
                    'photo': ('image.png', base64.b64decode(image_data.split(',')[1]), 'image/png')
                },
                timeout=30
            )
        else:
            # Для URL
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    'chat_id': chat_id,
                    'photo': image_data,
                    'caption': f"🎨 Gemini API: '{prompt}'"
                },
                timeout=30
            )
        
        if response.status_code == 200:
            logger.info(f"✅ Фото отправлено в Telegram")
        else:
            logger.error(f"❌ Ошибка отправки фото: {response.text}")
            send_message(chat_id, f"🎨 Сгенерировано! Ошибка отправки: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки фото: {e}")
        send_message(chat_id, f"🎨 Сгенерировано! Ошибка отправки")

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
    return "Бот работает! ✅ Google Gemini API"

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
