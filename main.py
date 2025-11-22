import os
import logging
import requests
import time
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
        # Правильный endpoint для генерации изображений
        url = "https://api.kie.ai/api/v1/flux/kontext/generate"
        
        headers = {
            "Authorization": f"Bearer {KIE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "prompt": prompt,
            "enableTranslation": True,  # Автоматический перевод на английский
            "aspectRatio": "1:1",       # Квадратное изображение
            "outputFormat": "png",
            "model": "flux-kontext-pro",
            "promptUpsampling": False,
            "safetyTolerance": 2
        }
        
        logger.info(f"🔄 Отправка в KIE API Flux Kontext...")
        response = requests.post(url, json=data, headers=headers, timeout=60)
        logger.info(f"📡 Ответ KIE: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"📦 Ответ: {result}")
            
            if result.get("code") == 200 and result.get("data"):
                task_id = result["data"]["taskId"]
                logger.info(f"✅ Задача создана: {task_id}")
                
                # Ждем завершения генерации и получаем результат
                return wait_for_image_result(task_id)
            else:
                logger.error(f"❌ Ошибка в ответе: {result}")
                return None
        else:
            logger.error(f"❌ Ошибка API: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        return None

def wait_for_image_result(task_id):
    """Ожидаем завершения генерации и получаем URL изображения"""
    try:
        url = f"https://api.kie.ai/api/v1/task/{task_id}"
        headers = {
            "Authorization": f"Bearer {KIE_API_KEY}"
        }
        
        # Ждем до 2 минут с проверками каждые 5 секунд
        for i in range(24):
            logger.info(f"⏳ Проверка задачи {task_id}... ({i+1}/24)")
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"📊 Статус задачи: {result}")
                
                if result.get("code") == 200 and result.get("data"):
                    task_data = result["data"]
                    status = task_data.get("status")
                    
                    if status == "completed":
                        # Изображение готово
                        if task_data.get("imageUrl"):
                            image_url = task_data["imageUrl"]
                            logger.info(f"🎉 Изображение готово: {image_url}")
                            return image_url
                    
                    elif status == "failed":
                        logger.error(f"❌ Задача провалилась: {task_data}")
                        return None
            
            time.sleep(5)  # Ждем 5 секунд перед следующей проверкой
        
        logger.error("❌ Таймаут ожидания задачи")
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка ожидания: {e}")
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
            send_message(chat_id, "📝 Напиши описание картинки на русском или английском\n\nПример: 'Кот в космосе с ракетой'")
            return
        
        # Генерация
        logger.info(f"🎨 Генерация: {text}")
        send_message(chat_id, f"🔄 Генерирую: '{text}'...\nЭто займет 1-2 минуты ⏳")
        
        image_url = generate_image(text)
        
        if image_url:
            logger.info(f"✅ Успех! Отправляем изображение...")
            send_telegram_photo(chat_id, image_url, text)
        else:
            logger.error("❌ Генерация не удалась")
            send_message(chat_id, "❌ Ошибка генерации. Попробуй другой запрос.")
            
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
            logger.info(f"✅ Фото отправлено в Telegram")
        else:
            logger.error(f"❌ Ошибка отправки фото: {response.text}")
            # Если не получилось отправить фото, отправляем ссылку
            send_message(chat_id, f"🎨 Сгенерировано! Ссылка: {image_url}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки фото: {e}")
        send_message(chat_id, f"🎨 Сгенерировано! Ссылка: {image_url}")

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
    return "Бот работает! ✅ Flux Kontext API"

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
