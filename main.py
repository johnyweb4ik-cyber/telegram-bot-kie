import os
import asyncio
import logging
from dotenv import load_dotenv
from io import BytesIO

# --- Импорты Aiogram ---
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile, Update
from aiogram.filters import Command
from aiohttp import web

# --- Импорты Google GenAI (по новой документации) ---
from google import genai
from google.genai import types
from PIL import Image

# --- 1. Настройка и Константы ---
load_dotenv()

# Переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 

# Render требует слушать 0.0.0.0 и порт из переменной PORT
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080)) 

# Выбор модели согласно вашей документации
# 'gemini-2.5-flash-image' - быстро, для обычных задач
# 'gemini-3-pro-image-preview' - высокое качество, понимание сложных инструкций
IMAGE_MODEL_NAME = "gemini-2.5-flash-image"

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot')

# --- 2. Класс для Генерации (Обновлен под GenAI SDK 0.3+) ---

class GeminiImageGenerator:
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            logger.error("❌ GEMINI_API_KEY не найден!")
            self.client = None
        else:
            # Инициализация клиента
            self.client = genai.Client(api_key=api_key)
            self.model = model_name
            logger.info(f"✅ Генератор инициализирован. Модель: {self.model}")

    def _generate_sync(self, prompt: str) -> bytes | None:
        """Синхронный метод генерации (выполняется в отдельном потоке)."""
        try:
            # Настройка конфига для получения изображения
            # Согласно документации: response_modalities=["TEXT", "IMAGE"] может потребоваться для редактирования,
            # но для простой генерации достаточно передать промпт.
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"] # Явно просим картинку
                )
            )

            # Парсинг ответа согласно новой документации
            # Ответ может содержать parts. Нам нужна та, где есть inline_data.
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        logger.info("Изображение получено из API.")
                        return part.inline_data.data # Это bytes
            
            logger.warning("API вернул ответ, но изображения в нем нет.")
            return None

        except Exception as e:
            logger.error(f"Ошибка при генерации: {e}")
            return None

    async def generate_image(self, prompt: str) -> bytes | None:
        """Асинхронная обертка, чтобы не блокировать бота."""
        if not self.client:
            return None
        
        logger.info(f"Генерация по промпту: {prompt}")
        # Запускаем синхронный вызов в отдельном потоке
        return await asyncio.to_thread(self._generate_sync, prompt)

# --- 3. Инициализация Бота ---

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
    exit(1)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
generator = GeminiImageGenerator(api_key=GEMINI_API_KEY, model_name=IMAGE_MODEL_NAME)

# --- 4. Хэндлеры (Обработчики команд) ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Привет! Я бот-художник на базе Gemini 2.5.</b>\n\n"
        "Напиши /photo <i>описание картинки</i>, чтобы создать шедевр.\n"
        "Пример: <code>/photo a futuristic cat in neon city</code>",
        parse_mode="HTML"
    )

@dp.message(Command("photo"))
async def cmd_photo(message: Message):
    # Проверка аргументов
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Пожалуйста, напиши описание после команды.\nПример: <code>/photo red apple</code>", parse_mode="HTML")
        return

    prompt = args[1]
    status_msg = await message.answer(f"🎨 <b>Рисую:</b> {prompt}\n⏳ <i>Подождите пару секунд...</i>", parse_mode="HTML")

    # Генерация
    image_bytes = await generator.generate_image(prompt)

    if image_bytes:
        # Отправка фото
        # BufferedInputFile нужен для отправки байтов напрямую из памяти
        photo_file = BufferedInputFile(image_bytes, filename="gemini_art.png")
        
        await message.answer_photo(
            photo=photo_file,
            caption=f"✨ <b>Готово!</b>\n📝 Промпт: {prompt}\n🤖 Модель: {IMAGE_MODEL_NAME}",
            parse_mode="HTML"
        )
        await status_msg.delete()
    else:
        await status_msg.edit_text("❌ Произошла ошибка при генерации. Возможно, запрос нарушает правила безопасности Google.")

# --- 5. Вебхуки и Запуск (Aiohttp) ---

async def handle_webhook(request: web.Request):
    """Обработка входящих запросов от Telegram."""
    url_token = request.match_info.get("token")
    if url_token != TELEGRAM_BOT_TOKEN:
        return web.Response(status=403)

    try:
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Ошибка вебхука: {e}")
        return web.Response(status=500)

async def handle_health(request: web.Request):
    """Простой healthcheck для Render (чтобы сервис не засыпал)."""
    return web.Response(text="I am alive!")

async def on_startup(app):
    """Действия при запуске приложения."""
    if WEBHOOK_URL:
        webhook_path = f"{WEBHOOK_URL}/webhook/{TELEGRAM_BOT_TOKEN}"
        await bot.set_webhook(webhook_path)
        logger.info(f"✅ Вебхук установлен: {webhook_path}")
    else:
        logger.warning("⚠️ WEBHOOK_URL не задан! Бот не будет получать обновления.")

async def on_shutdown(app):
    """Действия при остановке."""
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("🛑 Бот остановлен.")

def main():
    app = web.Application()
    
    # Маршруты
    app.router.add_post(f"/webhook/{{token}}", handle_webhook)
    app.router.add_get("/", handle_health) # Главная страница для проверки
    
    # Сигналы
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Запуск
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
