import os
import logging
import requests
from flask import Flask, request
from telegram import Bot, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

bot = Bot(token=BOT_TOKEN)

# Функция для генерации изображения через KIE API
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
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("images", [])[0] if result.get("images") else None
        else:
            logger.error(f"KIE API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return None

webhook_set = False

@app.route('/')
def home():
    global webhook_set
    RENDER_URL = "https://telegram-bot-kie.onrender.com"
    webhook_url = f"{RENDER_URL}/webhook"
    
    if not webhook_set:
        try:
            bot.set_webhook(webhook_url)
            logger.info(f"✅ Webhook установлен")
            webhook_set = True
            return "Бот работает! ✅ Генерация готова"
        except Exception as e:
            return f"Бот работает! ❌ Ошибка: {e}"
    else:
        return "Бот работает! ✅"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = Update.de_json(request.get_json(), bot)
        
        if update.message:
            chat_id = update.message.chat.id
            text = update.message.text
            
            if text == '/start':
                bot.send_message(
                    chat_id, 
                    "🎨 Привет! Я бот для генерации изображений через AI\n\n"
                    "Команды:\n"
                    "/generate - Создать изображение\n"
                    "/balance - Баланс\n"
                    "/help - Помощь"
                )
            elif text == '/help':
                bot.send_message(chat_id, "📖 Используй /generate и опиши картинку которую хочешь создать")
            elif text == '/balance':
                bot.send_message(chat_id, "💰 Баланс: 10 тестовых кредитов\nПополнение через админа")
            elif text == '/generate':
                bot.send_message(chat_id, "📝 Напиши описание картинки...\n\nНапример: 'Кот в скафандре в космосе'")
            elif text.startswith('/generate '):
                # Пользователь отправил /generate с текстом
                prompt = text.replace('/generate ', '')
                generate_and_send_image(chat_id, prompt)
            else:
                # Любой другой текст считаем промптом для генерации
                generate_and_send_image(chat_id, text)

def generate_and_send_image(chat_id, prompt):
    """Генерирует и отправляет изображение"""
    if not prompt.strip():
        bot.send_message(chat_id, "❌ Напиши описание картинки")
        return
        
    bot.send_message(chat_id, f"🔄 Генерирую: '{prompt}'...")
    
    image_url = generate_image(prompt)
    
    if image_url:
        bot.send_photo(chat_id, image_url, caption=f"🎨 Сгенерировано: '{prompt}'")
    else:
        bot.send_message(chat_id, "❌ Ошибка генерации. Попробуй другой запрос.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
