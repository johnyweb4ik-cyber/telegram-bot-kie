import os
import logging
from flask import Flask, request
from telegram import Bot, Update

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Получаем токены из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

# Создаем бота
bot = Bot(token=BOT_TOKEN)

# Устанавливаем вебхук при запуске
RENDER_URL = "https://telegram-bot-kie.onrender.com"  # ЗАМЕНИ на свой URL из Render
try:
    webhook_url = f"{RENDER_URL}/webhook"
    bot.set_webhook(webhook_url)
    print(f"✅ Webhook установлен: {webhook_url}")
except Exception as e:
    print(f"❌ Ошибка вебхука: {e}")

@app.route('/')
def home():
    return "Бот работает! ✅ Webhook: " + str(bot.get_webhook_info())

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = Update.de_json(request.get_json(), bot)
        
        # Обрабатываем сообщение
        if update.message:
            chat_id = update.message.chat.id
            text = update.message.text
            
            if text == '/start':
                bot.send_message(chat_id, "Привет! Я бот для генерации изображений. Отправь мне описание картинки.")
            else:
                bot.send_message(chat_id, f"Получил: '{text}'. Режим тестирования - скоро будет генерация!")
    
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
