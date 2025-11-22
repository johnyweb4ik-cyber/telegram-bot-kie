import os
import asyncio
import logging
from dotenv import load_dotenv

# Импорт из aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

# Импорт для работы с Google Generative AI (Gemini/Imagen)
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# --- 1. Настройка и Константы ---

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получение ключей из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # URL вашего сервиса на Render.com

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger('generator')

# Константы для Imagen
IMAGE_MODEL_NAME = "imagen-4.0-generate-001"
# Изображения генерируются в формате 1:1, размер 1024x1024 (по умолчанию)

# --- 2. Класс для Генерации Изображений ---

class ImageGenerator:
    """Класс для взаимодействия с Imagen API."""
    
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY не установлен.")
        self.client = genai.Client(api_key=api_key)
        self.model = model_name
        logger.info(f"Инициализирован генератор с моделью: {self.model}")
        
    async def generate_image(self, prompt: str) -> bytes | None:
        """Генерирует изображение по текстовому описанию и возвращает байты PNG."""
        
        # Конфигурация генерации
        config = types.GenerateImagesConfig(
            number_of_images=1,  # Генерируем одно изображение
            aspect_ratio="1:1"   # Квадратное изображение
        )
        
        logger.info(f"Запрос генерации изображения: {prompt}...")
        
        try:
            # Вызов API для генерации изображений
            response = await self.client.models.generate_images_async(
                model=self.model,
                prompt=prompt,
                config=config,
            )
            
            # Проверка, что изображение сгенерировано
            if not response.generated_images:
                logger.error("API вернул пустой список generated_images.")
                return None
                
            # Получение данных изображения в base64 и декодирование
            generated_image = response.generated_images[0]
            image_bytes = generated_image.image.image_bytes
            
            # Конвертация в PNG формат для Telegram
            img = Image.open(BytesIO(image_bytes))
            
            png_bytes = BytesIO()
            img.save(png_bytes, format='PNG')
            png_bytes.seek(0)
            
            return png_bytes.read()

        except Exception as e:
            # Логирование полной ошибки
            error_message = f"Ошибка API при генерации изображения: {e}"
            if hasattr(e, 'response') and e.response:
                 error_message += f". {e.response.status_code} {e.response.text}"
            logger.error(error_message)
            return None


# --- 3. Инициализация и Хэндлеры ---

# Инициализация бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Инициализация генератора
try:
    image_generator = ImageGenerator(api_key=GEMINI_API_KEY, model_name=IMAGE_MODEL_NAME)
except ValueError as e:
    logger.error(f"Ошибка инициализации: {e}")
    image_generator = None # Отключаем функционал, если ключа нет

@dp.message(Command("start"))
async def handle_start(message: Message):
    """Ответ на команду /start."""
    welcome_text = (
        "🤖 Привет! Я бот-генератор изображений.\n"
        "Чтобы сгенерировать изображение, используй команду:\n\n"
        "**/photo [ваше описание на английском]**\n\n"
        "Например: **/photo cat in space**"
    )
    await message.answer(welcome_text)

@dp.message(Command("photo"), F.text.regexp(r'/photo\s+(\S.*)'))
async def handle_photo(message: Message):
    """Обработка команды /photo с промптом."""
    
    if not image_generator:
        await message.answer("❌ Бот не может генерировать изображения. Проверьте API-ключ на сервере.")
        return

    # Получение промпта (текста после /photo)
    prompt = message.text.split(' ', 1)[1].strip()
    
    if not prompt:
        await message.answer("Пожалуйста, укажите описание для изображения после команды /photo.")
        return

    # Отправка сообщения о начале генерации
    status_message = await message.answer(f"⏳ Генерирую изображение по описанию: *{prompt}*...", parse_mode='Markdown')
    
    # Вызов генератора
    image_bytes = await image_generator.generate_image(prompt)
    
    # Удаление сообщения о статусе (опционально, для чистоты чата)
    await bot.delete_message(message.chat.id, status_message.message_id)

    if image_bytes:
        # Отправка изображения
        image_file = FSInputFile(BytesIO(image_bytes), filename='generated_image.png')
        await message.answer_photo(
            photo=image_file,
            caption=f"✅ Изображение готово! Промпт: *{prompt}*",
            parse_mode='Markdown'
        )
    else:
        # Ответ в случае ошибки
        await message.answer(
            "❌ Не удалось сгенерировать изображение. Пожалуйста, попробуйте другое описание или обратитесь к администратору (проверьте логи)."
        )

@dp.message(Command("photo"))
async def handle_photo_no_prompt(message: Message):
    """Обработка команды /photo без промпта."""
    await message.answer("Пожалуйста, укажите описание для изображения после команды /photo.\n\nПример: **/photo a dog wearing glasses**")


# --- 4. Запуск Сервера ---

async def main():
    """Основная функция запуска бота."""
    
    # 1. Проверка ключей
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY or not WEBHOOK_URL:
        logger.error("Одна или несколько необходимых переменных окружения (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, WEBHOOK_URL) не установлены.")
        return

    logger.info("Инициализация генератора и установка Webhook...")

    # 2. Установка Webhook
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{TELEGRAM_BOT_TOKEN}")
    logger.info(f"Webhook установлен на URL: {WEBHOOK_URL}/webhook/{TELEGRAM_BOT_TOKEN}")

    # 3. Запуск диспетчера
    # dp.run_polling(bot) не подходит для Render.com
    # Мы используем встроенный aiohttp-сервер для обработки POST-запросов от Telegram
    from aiohttp import web
    
    # URL-путь для приема обновлений
    webhook_path = f"/webhook/{TELEGRAM_BOT_TOKEN}"
    
    # Создание HTTP-приложения
    app = web.Application()
    
    # Добавление хэндлера для Telegram обновлений
    app.router.add_post(webhook_path, dp.create_request_handler(bot))
    
    # Запуск сервера на порту 10000 (стандарт для Render.com)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    
    try:
        await site.start()
        logger.info("======== Running on http://0.0.0.0:10000 ========")
        # Удерживаем main() в рабочем состоянии
        await asyncio.Event().wait() 
    finally:
        # Очистка Webhook при завершении
        await bot.delete_webhook()
        logger.info("Webhook удален.")
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}")
