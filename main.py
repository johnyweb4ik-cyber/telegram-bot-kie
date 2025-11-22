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
        url = "https://api.kie.ai/api/v1/flux/kontext/generate"
        
        headers = {
            "Authorization": f"Bearer {KIE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "prompt": prompt,
            "enableTranslation": True,
            "aspectRatio": "1:1",
            "outputFormat": "png",
            "model": "flux-kontext-pro",
            "promptUpsampling": False,
            "safetyTolerance": 2
        }
        
        logger.info(f"🔄 Отправка в KIE API...")
        response = requests.post(url, json=data, headers=headers, timeout=60)
        logger.info(f"📡 Ответ KIE: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"📦 Ответ: {result}")
            
            if result.get("code") == 200 and result.get("data"):
                task_id = result["data"]["taskId"]
                logger.info(f"✅ Задача создана: {task_id}")
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
    """Ожидаем завершения генерации"""
    try:
        url = f"https://api.kie.ai/api/v1/task/{task_id}"
        headers = {
            "Authorization": f"Bearer {KIE_API_KEY}"
        }
        
        # Ждем до 3 минут с проверками каждые 10 секунд
        for i in range(18):  # 18 * 10 сек = 3 минуты
            logger.info(f"⏳ Проверка задачи {task_id}... ({i+1}/18)")
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"📊 Статус ответа: {result}")
                    
                    # Проверяем разные возможные структуры ответа
                    if result.get("code") == 200:
                        data = result.get("data", {})
                        
                        # Проверяем статус задачи
                        status = data.get("status")
                        logger.info(f"📋 Статус задачи: {status}")
                        
                        if status == "completed":
                            # Ищем URL изображения в разных возможных полях
                            image_url = (data.get("imageUrl") or 
                                       data.get("url") or 
                                       data.get("image_url"))
                            
                            if image_url:
                                logger.info(f"🎉 Изображение готово: {image_url}")
                                return image_url
                            else:
                                logger.info(f"📋 Данные completed задачи: {data}")
                        
                        elif status == "failed":
                            error_msg = data.get("error", "Неизвестная ошибка")
                            logger.error(f"❌ Задача провалилась: {error_msg}")
                            return None
                        
                        elif status == "processing":
                            logger.info("🔄 Задача в процессе...")
                            # Продолжаем ждать
                            
                        else:
                            logger.info(f"📋 Неизвестный статус: {status}")
                            logger.info(f"📋 Полные данные: {data}")
                    
                    else:
                        logger.error(f"❌ Ошибка в ответе задачи: {result}")
                
                else:
                    logger.error(f"❌ Ошибка HTTP: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки задачи: {e}")
            
            time.sleep(10)  # Ждем 10 секунд перед следующей проверкой
        
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
            send_message(chat_id, "📝 Напиши описание картинки\n\nПример: 'Кот в космосе с ракетой'")
            return
        
        # Генерация
        logger.info(f"🎨 Генерация: {text}")
        send_message(chat_id, f"🔄 Генерирую: '{text}'...\nЭто займет 1-3 минуты ⏳")
        
        image_url = generate_image(text)
        
        if image_url:
            logger.info(f"✅ Успех! Отправляем изображение...")
            send_telegram_photo(chat_id, image_url, text)
        else:
            logger.error("❌ Генерация не удалась")
            send_message(chat_id, "❌ Ошибка генерации. Попробуй другой запрос или позже.")
            
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
