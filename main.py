import os
import asyncio
import logging
from dotenv import load_dotenv
from io import BytesIO

# --- Импорты Aiogram и Google GenAI ---
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiohttp import web

from google import genai
from google.genai import types
from PIL import Image

# --- 1. Настройка и Константы ---

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получение ключей из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 10000)) # Порт 10000 для Render.com

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger('generator')

# Константы для Imagen
IMAGE_MODEL_NAME = "imagen-4.0-generate-001"
# Формируем полный путь вебхука
WEBHOOK_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}"

# --- 2. Класс для Генерации Изображений ---

class ImageGenerator:
    """Класс для взаимодействия с Imagen API."""
    
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            logger.error("GEMINI_API_KEY не установлен.")
            self.client = None
            return
            
        self.client = genai.Client(api_key=api_key)
        self.model = model_name
        logger.info(f"Инициализирован генератор с моделью: {self.model}")
        
    async def generate_image(self, prompt: str) -> bytes | None:
        """Генерирует изображение по текстовому описанию и возвращает байты PNG."""
        
        if not self.client:
            return None
        
        # Конфигурация генерации
        config = types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1"
        )
        
        logger.info(f"Запрос генерации изображения: {prompt}...")
        
        try:
            # Вызов API для генерации изображений
            response = await self.client.models.generate_images_async(
                model=self.model,
                prompt=prompt,
                config=config,
            )
            
            if not response.generated_images:
                logger.error("API вернул пустой список generated_images.")
                return None
                
            generated_image = response.generated_images[0]
            image_bytes = generated_image.image.image_bytes
            
            # Конвертация в PNG формат для Telegram
            img = Image.open(BytesIO(image_bytes))
            png_bytes = BytesIO()
            img.save(png_bytes, format='PNG')
            png_bytes.seek(0)
            
            return png_bytes.read()

        except Exception as e:
            error_message = f"Ошибка API при генерации изображения: {e}"
            if hasattr(e, 'response') and e.response:
                 error_message += f". Status: {e.response.status_code}, Text: {e.response.text}"
            logger.error(error_message)
            return None


# --- 3. Инициализация и Хэндлеры ---

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Инициализация генератора
image_generator = ImageGenerator(api_key=GEMINI_API_KEY, model_name=IMAGE_MODEL_NAME)


@dp.message(Command("start"))
async def handle_start(message: Message):
    """Ответ на команду /start."""
    welcome_text = (
        "🤖 Привет! Я бот-генератор изображений.\n"
        "Чтобы сгенерировать изображение, используй команду:\n\n"
        "**/photo [ваше описание на английском]**\n\n"
        "Например: **/photo a majestic wolf in the snow, hyperrealistic**"
    )
    await message.answer(welcome_text, parse_mode='Markdown')

@dp.message(Command("photo"), F.text.regexp(r'/photo\s+(\S.*)'))
async def handle_photo(message: Message):
    """Обработка команды /photo с промптом."""
    
    if not image_generator.client:
        await message.answer("❌ Бот не может генерировать изображения. Проверьте API-ключ Google.")
        return

    prompt = message.text.split(' ', 1)[1].strip()
    
    if not prompt:
        await message.answer("Пожалуйста, укажите описание для изображения после команды /photo.")
        return

    status_message = await message.answer(f"⏳ Генерирую изображение по описанию: *{prompt}*...", parse_mode='Markdown')
    
    image_bytes = await image_generator.generate_image(prompt)
    
    await bot.delete_message(message.chat.id, status_message.message_id)

    if image_bytes:
        image_file = FSInputFile(BytesIO(image_bytes), filename='generated_image.png')
        await message.answer_photo(
            photo=image_file,
            caption=f"✅ Изображение готово! Промпт: *{prompt}*",
            parse_mode='Markdown'
        )
    else:
        await message.answer(
            "❌ Не удалось сгенерировать изображение. Пожалуйста, попробуйте другое описание или проверьте логи сервера."
        )

@dp.message(Command("photo"))
async def handle_photo_no_prompt(message: Message):
    """Обработка команды /photo без промпта."""
    await message.answer("Пожалуйста, укажите описание для изображения после команды /photo.\n\nПример: **/photo a robot holding a red skateboard**")


# --- 4. Запуск Сервера (Функция main) ---

async def main():
    """Основная функция запуска бота, настроенная для Webhook на Render.com."""
    
    # 1. Проверка ключей
    if not TELEGRAM_BOT_TOKEN or not WEBHOOK_URL:
        logger.error("❌ Не установлены TELEGRAM_BOT_TOKEN или WEBHOOK_URL. Проверьте настройки Render.")
        return
    
    logger.info("Инициализация генератора и установка Webhook...")
    
    # 2. Установка Webhook URL
    full_webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(url=full_webhook_url)
    logger.info(f"Webhook установлен на URL: {full_webhook_url}")

    # 3. Настройка и запуск aiohttp-сервера
    app = web.Application()
    
    # !!! ИСПРАВЛЕННАЯ СТРОКА: Использование dp.get_web_app_factory() для Aiogram v3 !!!
    app.router.add_route(
        "POST", WEBHOOK_PATH, dp.get_web_app_factory()
    )
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Запуск сервера
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    
    try:
        await site.start()
        logger.info(f"======== Running on http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT} ========")
        # Удерживаем main() в рабочем состоянии
        await asyncio.Event().wait() 
    finally:
        # Очистка Webhook и ресурсов при завершении
        await bot.delete_webhook()
        logger.info("Webhook удален. Очистка завершена.")
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}")
