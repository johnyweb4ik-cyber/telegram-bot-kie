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
            logger.info(f"📦 Ответ создания задачи: {result}")
            
            if result.get("code") == 200 and result.get("data"):
                task_id = result["data"]["taskId"]
                logger.info(f"✅ Задача создана: {task_id}")
                
                # Ждем 10 секунд перед первой проверкой (возможно задача индексируется)
                logger.info("⏳ Ждем 10 секунд перед первой проверкой...")
                time.sleep(10)
                
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
    """Пробуем разные endpoints для проверки статуса"""
    
    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}"
    }
    
    # Пробуем разные возможные endpoints
    endpoints_to_try = [
        {
            "url": "https://api.kie.ai/api/v1/flux/kontext/record-info",
            "params": {"taskId": task_id},
            "method": "GET"
        },
        {
            "url": f"https://api.kie.ai/api/v1/task/{task_id}",
            "params": {},
            "method": "GET"
        },
        {
            "url": "https://api.kie.ai/api/v1/task/status",
            "params": {"taskId": task_id},
            "method": "GET"
        },
        {
            "url": f"https://api.kie.ai/api/v1/flux/kontext/task/{task_id}",
            "params": {},
            "method": "GET"
        }
    ]
    
    logger.info(f"🔍 Начинаем отслеживание задачи: {task_id}")
    
    # Ждем до 5 минут с проверками каждые 15 секунд
    for check_count in range(20):  # 20 * 15 сек = 5 минут
        logger.info(f"⏳ Проверка {check_count+1}/20 задачи: {task_id}")
        
        for endpoint in endpoints_to_try:
            try:
                logger.info(f"🔧 Пробуем endpoint: {endpoint['url']}")
                
                if endpoint["method"] == "GET":
                    response = requests.get(
                        endpoint["url"], 
                        headers=headers, 
                        params=endpoint["params"], 
                        timeout=30
                    )
                else:
                    response = requests.post(
                        endpoint["url"],
                        headers=headers,
                        json=endpoint["params"],
                        timeout=30
                    )
                
                logger.info(f"📡 HTTP статус: {response.status_code} для {endpoint['url']}")
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"📊 Успешный ответ от {endpoint['url']}:")
                    logger.info(f"📊 Код: {result.get('code')}")
                    logger.info(f"📊 Данные: {result.get('data')}")
                    
                    # Проверяем разные возможные структуры ответа
                    if result.get("code") == 200:
                        data = result.get("data", {})
                        
                        # Пробуем извлечь статус разными способами
                        success_flag = data.get("successFlag")
                        status = data.get("status")
                        state = data.get("state")
                        
                        logger.info(f"📋 successFlag: {success_flag}, status: {status}, state: {state}")
                        
                        # Если задача завершена
                        if (success_flag == 1 or status in ["completed", "success"] or 
                            state in ["completed", "success"]):
                            
                            # Ищем URL изображения в разных возможных полях
                            response_data = data.get("response", {})
                            image_url = (response_data.get("resultImageUrl") or 
                                       response_data.get("originImageUrl") or
                                       data.get("imageUrl") or
                                       data.get("url") or
                                       response_data.get("url"))
                            
                            if image_url:
                                logger.info(f"🎉 Изображение готово: {image_url}")
                                return image_url
                        
                        # Если задача провалилась
                        elif (success_flag == 2 or status in ["failed", "error"] or 
                              state in ["failed", "error"]):
                            error_msg = data.get("errorMessage", data.get("error", "Неизвестная ошибка"))
                            logger.error(f"❌ Задача провалилась: {error_msg}")
                            return None
                
                elif response.status_code == 404:
                    logger.info(f"📋 Endpoint не найден: {endpoint['url']}")
                    # Продолжаем пробовать другие endpoints
                    continue
                    
                else:
                    logger.info(f"📋 Другой статус {response.status_code} для {endpoint['url']}: {response.text}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки {endpoint['url']}: {e}")
        
        # Ждем 15 секунд перед следующей проверкой
        logger.info("⏳ Ждем 15 секунд...")
        time.sleep(15)
    
    logger.error("❌ Таймаут ожидания задачи")
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
        send_message(chat_id, f"🔄 Генерирую: '{text}'...\nЭто займет 1-5 минут ⏳")
        
        image_url = generate_image(text)
        
        if image_url:
            if image_url.startswith(('http://', 'https://')):
                logger.info(f"✅ Успех! Отправляем изображение...")
                send_telegram_photo(chat_id, image_url, text)
            else:
                logger.info(f"📋 Результат: {image_url}")
                send_message(chat_id, f"📋 Статус: {image_url}")
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
