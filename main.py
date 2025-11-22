import os
import logging
import requests
import time
import json
import base64
from flask import Flask, request
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = "AIzaSyCJXtPnJsFlEilLgJEZzCqtN3klDZrotWE"

# Настройка Gemini API
genai.configure(api_key=GEMINI_API_KEY)

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
    """Генерация изображения через Gemini API"""
    try:
        # Сначала создаем улучшенный промпт на английском
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        enhancement_prompt = f"""
        Создай детальное описание на английском для генерации изображения: "{prompt}"
        
        Верни ТОЛЬКО описание на английском без дополнительного текста.
        Сделай описание креативным и детализированным.
        """
        
        logger.info(f"🔄 Создаем улучшенный промпт...")
        enhancement_response = model.generate_content(enhancement_prompt)
        
        if not enhancement_response.text:
            logger.error("❌ Не удалось создать промпт")
            return None
            
        english_prompt = enhancement_response.text.strip()
        logger.info(f"📝 Английский промпт: {english_prompt}")
        
        # Теперь генерируем изображение через Imagen 3
        return generate_with_imagen3(english_prompt)
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания промпта: {e}")
        return None

def generate_with_imagen3(prompt):
    """Генерация через Imagen 3 REST API с правильной структурой"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:generateContent?key={GEMINI_API_KEY}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        # ПРАВИЛЬНАЯ структура для Imagen 3
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generation_config": {
                "number_of_images": 1,  # Правильное имя параметра
                "aspect_ratio": "1:1"   # Правильное имя параметра
            }
        }
        
        logger.info(f"🔄 Отправка запроса к Imagen 3...")
        response = requests.post(url, headers=headers, json=data, timeout=60)
        logger.info(f"📡 Ответ Imagen 3: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ Изображение сгенерировано")
            
            # Парсим ответ
            if "candidates" in result and result["candidates"]:
                candidate = result["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inlineData" in part:
                            image_data = part["inlineData"]["data"]
                            return f"data:image/png;base64,{image_data}"
            
            # Если не нашли изображение, логируем структуру
            logger.info(f"📋 Структура ответа: {json.dumps(result, indent=2)[:500]}...")
            return "Изображение создано, но не найден URL в ответе"
            
        else:
            error_text = response.text
            logger.error(f"❌ Ошибка Imagen 3: {error_text}")
            
            # Проверяем конкретные ошибки
            if "quota" in error_text.lower():
                return "❌ Закончилась квота API. Проверь лимиты в Google AI Studio."
            elif "invalid" in error_text.lower():
                return "❌ Неверный запрос или параметры. Попробуй другой промпт."
            else:
                return f"❌ Ошибка API: {error_text[:100]}"
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        return None

def test_gemini_connection():
    """Тестируем подключение к Gemini API"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Ответь одним словом: работает")
        
        logger.info(f"✅ Gemini API работает: {response.text}")
        return True, response.text
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Gemini: {e}")
        return False, str(e)

def process_message(chat_id, text):
    logger.info(f"🔧 Обработка: {text}")
    
    try:
        if text == '/start':
            send_message(chat_id, 
                "🎨 Бот для генерации изображений!\n\n"
                "✨ Используем Google Gemini API\n"
                "🚀 Технология Imagen 3\n"
                "📝 Просто напиши описание картинки на русском\n\n"
                "Команды:\n"
                "/generate - создать изображение\n" 
                "/help - помощь\n"
                "/test - тест API\n"
                "/balance - информация"
            )
            return
            
        if text == '/test':
            send_message(chat_id, "🔄 Тестируем подключение к Google AI...")
            success, result = test_gemini_connection()
            if success:
                send_message(chat_id, f"✅ API ключ работает! Ответ: {result}\n\nМожем генерировать изображения! 🚀")
            else:
                send_message(chat_id, f"❌ Проблема с API: {result}")
            return
            
        if text == '/balance':
            send_message(chat_id, 
                "💰 Google Gemini API:\n\n"
                "• Бесплатный лимит: 60 запросов/мин\n"
                "• Генерация изображений: через Imagen 3\n"
                "• Проверь квоты: https://aistudio.google.com/\n"
                "• Ключ активен: ✅"
            )  
            return
            
        if text in ['/help', '/generate']:
            send_message(chat_id, 
                "📝 Напиши описание картинки на русском:\n\n"
                "🖼️ Примеры:\n"
                "• 'Кот в космосе в скафандре'\n" 
                "• 'Футуристический город ночью с неоновыми огнями'\n"
                "• 'Закат на тропическом пляже с пальмами'\n"
                "• 'Робот читает книгу в античной библиотеке'\n"
                "• 'Единорог в волшебном лесу с радугой'"
            )
            return
        
        # Генерация изображения
        logger.info(f"🎨 Генерация: {text}")
        send_message(chat_id, 
            f"🔄 Генерирую: '{text}'...\n\n"
            "Этапы обработки:\n"
            "1. 📝 Создаю детальный промпт\n"
            "2. 🎨 Генерирую изображение через Imagen 3\n"
            "3. 📤 Отправляю результат\n"
            "⏳ Ожидайте 10-20 секунд..."
        )
        
        image_data = generate_image_gemini(text)
        
        if image_data:
            if image_data.startswith('data:image'):
                logger.info(f"✅ Успех! Отправляем изображение...")
                send_telegram_photo(chat_id, image_data, text)
            else:
                logger.info(f"📋 Результат: {image_data}")
                send_message(chat_id, f"📋 Статус: {image_data}")
        else:
            logger.error("❌ Генерация не удалась")
            send_message(chat_id, 
                "❌ Ошибка генерации\n\n"
                "Возможные причины:\n"
                "• 🔑 Проблема с API ключом\n"
                "• 📝 Неподдерживаемый запрос\n"
                "• 💰 Закончилась квота\n"
                "• 🌐 Проблемы с сетью\n\n"
                "Попробуй:\n"
                "• Использовать /test для проверки\n"
                "• Другой запрос\n"
                "• Подождать немного"
            )
            
    except Exception as e:
        logger.error(f"💥 Ошибка: {e}")
        send_message(chat_id, "❌ Произошла неожиданная ошибка")

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
                    'caption': f"🎨 Сгенерировано: '{prompt}'\n✨ Google Imagen 3"
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
                send_message(chat_id, "✅ Изображение сгенерировано, но ошибка отправки в Telegram")
                
        else:
            send_message(chat_id, f"📋 Результат: {image_data}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки фото: {e}")
        send_message(chat_id, "✅ Изображение сгенерировано, но ошибка отправки")

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
