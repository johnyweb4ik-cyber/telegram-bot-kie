import os
import logging
from flask import Flask, request
from telegram import Bot, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
KIE_API_KEY = os.environ.get('KIE_API_KEY')

bot = Bot(token=BOT_TOKEN)

# Устанавливаем меню команд
try:
    bot.set_my_commands([
        ("start", "Запустить бота"),
        ("help", "Помощь"),
        ("generate", "Сгенерировать изображение"),
        ("balance", "Проверить баланс")
    ])
    logger.info("✅ Меню команд установлено")
except Exception as e:
    logger.error(f"❌ Ошибка меню: {e}")

# Флаг для отслеживания установки вебхука
webhook_set = False

@app.route('/')
def home():
    global webhook_set
    RENDER_URL = "https://telegram-bot-kie.onrender.com"
    webhook_url = f"{RENDER_URL}/webhook"
    
    if not webhook_set:
        try:
            bot.set_webhook(webhook_url)
            logger.info(f"✅ Webhook установлен: {webhook_url}")
            webhook_set = True
            return "Бот работает! ✅ Вебхук установлен, меню настроено"
        except Exception as e:
            return f"Бот работает! ❌ Ошибка вебхука: {e}"
    else:
        return "Бот работает! ✅ Вебхук уже установлен, меню настроено"

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
                    "🎨 Привет! Я бот для генерации изображений через AI.\n\n"
                    "Доступные команды:\n"
                    "/generate - Сгенерировать изображение\n"
                    "/balance - Проверить баланс\n"
                    "/help - Помощь"
                )
            elif text == '/help':
                bot.send_message(
                    chat_id,
                    "🤖 Помощь по боту:\n\n"
                    "1. Используй /generate для создания изображений\n"
                    "2. Баланс можно пополнить через админа\n"
                    "3. Просто отправь описание картинки после команды /generate"
                )
            elif text == '/balance':
                bot.send_message(chat_id, "💰 Твой баланс: 0 кредитов\n\nДля пополнения обратись к админу.")
            elif text == '/generate':
                bot.send_message(chat_id, "📝 Отправь описание картинки которую хочешь сгенерировать.\n\nНапример: 'Кот в космосе' или 'Город будущего'")
            else:
                bot.send_message(chat_id, f"🔮 Скоро я научусь генерировать картинки по запросу: '{text}'\n\nПока используй команды из меню!")
    
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
