import os
import logging
import requests
import time
import json
import base64
from flask import Flask, request
from google import genai
from google.genai import types
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = "AIzaSyCJXtPnJsFlEilLgJEZzCqtN3klDZrotWE"

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

def generate_image_imagen3(prompt):
    """Генерация через Imagen 3 используя официальную библиотеку"""
    try:
        # Инициализация клиента
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        logger.info(f"🔄 Генерация через Imagen 3...")
        
        # Генерация изображения
        response = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio='1:1'
            )
        )
        
        logger.info(f"✅ Изображение сгенерировано")
        
        # Конвертируем в base64 для Telegram
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            return f"data:image/png;base64,{image_base64}"
        else:
            logger.error("❌ Нет сгенерированных изображений")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации через Imagen 3: {e}")
        return None

def test_gemini_text():
    """Тестируем текстовую модель чтобы проверить подключение"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Ответь одним словом: работает"
        )
        
        logger.info(f"✅ Текстовая модель работает: {response.text}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Текстовая модель не работает: {e}")
        return False

def process_message(chat_id, text):
    logger.info(f"🔧 Обработка: {text}")
    
    try:
        if text == '/start':
            send_message(chat_id, 
                "🎨 Бот для генерации изображений!\n\n"
                "✨ Используем Google Imagen 3\n"
                "📝 Просто напиши описание картинки\n\n"
                "Команды:\n"
                "/generate - создать изображение\n" 
                "/help - помощь\n"
                "/test - тест API"
            )
            return
            
        if text == '/test':
            send_message(chat_id, "🔄 Тестируем подключение к Google AI...")
            if test_gemini_text():
                send_message(chat_id, "✅ API ключ работает! Можем генерировать изображения 🚀")
            else:
                send_message(chat_id, "❌ Проблема с API ключом. Проверь ключ и попробуй снова.")
            return
            
        if text in ['/help', '/generate']:
            send_message(chat_id, 
                "📝 Напиши описание картинки\n\n"
                "Примеры:\n"
                "• 'Кот в космосе в скафандре'\n" 
                "• 'Футуристический город ночью'\n"
                "• 'Закат на тропическом пляже'\n"
                "• 'Робот читает книгу в библиотеке'"
            )
            return
        
        # Генерация изображения
        logger.info(f"🎨 Генерация: {text}")
        send_message(chat_id, f"🔄 Генерирую: '{text}'...\nИспользую Google Imagen 3 🚀")
        
        image_data = generate_image_imagen3(text)
        
        if image_data:
            logger.info(f"✅ Успех! Отправляем изображение...")
            send_telegram_photo(chat_id, image_data, text)
        else:
            logger.error("❌ Генерация не удалась")
            send_message(chat_id, 
                "❌ Ошибка генерации\n\n"
                "Возможные причины:\n"
                "• Неподдерживаемый запрос\n"
                "• Проблема с API ключом\n"
                "• Используй /test для проверки\n"
                "• Попробуй другой запрос"
            )
            
    except Exception as e:
        logger.error(f"💥 Ошибка: {e}")
        send_message(chat_id, "❌ Произошла ошибка при генерации")

def send_telegram_photo(chat_id, image_data, prompt):
    """Отправка фото в Telegram"""
    try:
        if image_data.startswith('data:image'):
            # Декодируем base64 и отправляем как файл
            image_bytes = base64.b64decode(image_data.split(',')[1])
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={
                    'chat_id': chat_id,
                    'caption': f"🎨 Google Imagen 3: '{prompt}'"
                },
                files={
                    'photo': ('image.png', image_bytes, 'image/png')
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Фото отправлено в Telegram")
            else:
                logger.error(f"❌ Ошибка отправки фото: {response.text}")
                send_message(chat_id, f"✅ Изображение сгенерировано, но ошибка отправки")
                
        else:
            # Если это URL
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    'chat_id': chat_id,
                    'photo': image_data,
                    'caption': f"🎨 Google Imagen 3: '{prompt}'"
                },
                timeout=30
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки фото: {e}")
        send_message(chat_id, f"✅ Изображение сгенерировано, но ошибка отправки")

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
    return "Бот работает! ✅ Google Imagen 3"

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
