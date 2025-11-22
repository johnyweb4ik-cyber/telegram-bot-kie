import os
import logging
import requests
import asyncio
from flask import Flask, request
from telegram import Bot, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

logger.info(f"BOT_TOKEN exists: {BOT_TOKEN is not None}")

# Создаем бота
bot = Bot(token=BOT_TOKEN)

# Устанавливаем вебхук асинхронно
async def setup_webhook():
    try:
        RENDER_URL = "https://telegram-bot-kie.onrender.com"
        webhook_url = f"{RENDER_URL}/webhook"
        await bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Ошибка вебхука: {e}")

# Запускаем установку вебхука при старте
asyncio.run(setup_webhook())

@app.route('/')
def home():
    return "Бот работает! ✅ Вебхук настроен"

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("📨 Получен запрос от Telegram")
    
    if request.method == 'POST':
        try:
            update_data = request.get_json()
            logger.info(f"📦 Данные: {update_data}")
            
            update = Update.de_json(update_data, bot)
            
            if update.message:
                chat_id = update.message.chat.id
                text = update.message.text
                logger.info(f"💬 Сообщение: {text} от {chat_id}")
                
                # Обрабатываем синхронно
                if text == '/start':
                    bot.send_message(chat_id, "🎨 Бот работает! Команды активны")
                elif text == '/help':
                    bot.send_message(chat_id, "📖 Помощь: используй команды из меню")
                elif text == '/balance':
                    bot.send_message(chat_id, "💰 Баланс: 10 кредитов")
                elif text == '/generate':
                    bot.send_message(chat_id, "📝 Опиши картинку...")
                else:
                    bot.send_message(chat_id, f"📝 Получил: {text}")
            
            return 'ok'
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return 'error'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
