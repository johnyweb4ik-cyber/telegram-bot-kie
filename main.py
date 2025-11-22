import os
import logging
import asyncio
import base64
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile
from aiogram.filters import Command # <-- ИСПРАВЛЕНИЕ: Импортируем Command из aiogram.filters
from google import genai
from google.genai.errors import APIError
from aiohttp import web 

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения (для локального запуска)
load_dotenv()

# --- Константы и конфигурация ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Модели
TEXT_MODEL = "gemini-2.5-flash-preview-09-2025"  
IMAGE_MODEL = "gemini-2.5-flash-image"         

# Системная инструкция для улучшения промпта (Про́мпт-инженер)
PROMPT_ENHANCER_SYSTEM_INSTRUCTION = (
    "You are a highly skilled prompt engineer and translator. "
    "Your task is to take a user's prompt, which may be short, vague, or in Russian, and transform it "
    "into a detailed, artistic, and evocative image generation prompt in **perfect English**. "
    "You must add style, detail, and artistic flair (e.g., 'hyper-realistic', 'cinematic lighting', 'digital painting'). "
    "Do not include any commentary, explanations, or extraneous text. "
    "Respond ONLY with the enhanced English prompt."
)

# Инициализация Gemini
gemini_client = None
if not GEMINI_API_KEY:
    logger.error("Переменная GEMINI_API_KEY не найдена!")
else:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"✅ Генератор Gemini инициализирован.")
    except Exception as e:
         logger.error(f"Ошибка инициализации Gemini: {e}")

# Инициализация Telegram Bot
if not TELEGRAM_BOT_TOKEN:
    logger.error("Переменная TELEGRAM_BOT_TOKEN не найдена!")
    exit(1)
dp = Dispatcher()
bot = Bot(token=TELEGRAM_BOT_TOKEN, 
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# --- Хэндлеры ---

@dp.message(Command("start")) # <-- ИСПРАВЛЕНИЕ
async def handle_start(message: types.Message):
    """Обрабатывает команду /start, отправляя приветственное сообщение."""
    greeting_text = (
        "👋 **Привет! Я бот-генератор изображений на базе Gemini AI.**\n\n"
        "Чтобы создать картинку, используйте команду `/photo` и добавьте описание.\n"
        "Вы можете писать на **русском** или **английском** – я автоматически улучшу и переведу ваш промпт!\n\n"
        "**Пример:**\n"
        "`/photo Кот в очках на красной крыше`"
    )
    await message.answer(greeting_text)

@dp.message(Command("photo")) # <-- ИСПРАВЛЕНИЕ
async def handle_photo(message: types.Message):
    """
    Основной хэндлер. 
    1. Улучшает и переводит промпт (с русского на английский). 
    2. Генерирует изображение.
    """
    
    if not gemini_client:
        await message.answer("❌ **Ошибка:** Сервис генерации изображений не инициализирован (проверьте GEMINI_API_KEY).")
        return
        
    # Извлекаем промпт, чтобы не зависеть от синтаксиса Command
    if message.text.lower().startswith('/photo'):
        original_prompt = message.text[len('/photo'):].strip()
    else:
        # Это запасной вариант, если Command пропустит что-то неожиданное
        original_prompt = message.text.strip()


    if not original_prompt:
        await message.answer("❌ **Ошибка:** Пожалуйста, укажите описание для изображения после команды `/photo`.\n"
                             "Пример: `/photo Уютная, маленькая библиотека под дождем`")
        return

    logger.info(f"Получен промпт: {original_prompt} от пользователя {message.from_user.id}")

    # Отправка сообщения о начале генерации для обратной связи
    status_message = await message.answer(f"🤖 **Начинаю работу.**\n\n"
                                         f"1. Улучшаю и перевожу ваш промпт...")

    enhanced_prompt = original_prompt # Инициализируем на случай ошибки

    try:
        # --- Шаг 1: Улучшение и перевод промпта (Текстовая модель) ---
        text_response = gemini_client.models.generate_content(
            model=TEXT_MODEL,
            contents=[original_prompt],
            system_instruction=PROMPT_ENHANCER_SYSTEM_INSTRUCTION
        )
        
        enhanced_prompt = text_response.text.strip()
        logger.info(f"Улучшенный промпт: {enhanced_prompt}")

        # Обновляем сообщение о статусе, чтобы показать, что будет генерироваться
        await bot.edit_message_text(
            chat_id=status_message.chat.id,
            message_id=status_message.message_id,
            text=f"🤖 **Промпт улучшен!**\n\n"
                 f"Ваше описание: *{original_prompt}*\n"
                 f"Используемый промпт: `{enhanced_prompt}`\n\n"
                 f"2. Генерирую изображение (это может занять до 15 секунд)..."
        )
        
        # --- Шаг 2: Генерация изображения (Графическая модель) ---
        image_response = gemini_client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[enhanced_prompt],
            config={"response_modality": "IMAGE"}
        )
        
        # --- Шаг 3: Обработка и отправка изображения ---
        candidate = image_response.candidates[0] if image_response.candidates else None
        
        if candidate and candidate.content and candidate.content.parts and candidate.content.parts[0].inline_data:
            logger.info("Изображение получено из API.")
            
            # Декодирование base64 данных изображения
            image_data_base64 = candidate.content.parts[0].inline_data.data
            image_bytes = base64.b64decode(image_data_base64)
            
            # Отправка изображения в Telegram
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=BufferedInputFile(image_bytes, filename="generated_image.png"),
                caption=f"✅ Готово! Изображение сгенерировано на основе промпта:\n`{enhanced_prompt}`"
            )
            
        else:
            # Обработка ошибок, если данные изображения отсутствуют
            finish_reason = candidate.finish_reason.name if candidate and candidate.finish_reason else "UNKNOWN"
            
            if finish_reason == "SAFETY":
                 error_message = f"🚫 **Ошибка безопасности.** Запрос был заблокирован из-за политики контента."
            else:
                 error_message = (
                    f"❌ **Ошибка генерации ({finish_reason}):** Не удалось создать изображение. "
                    f"Попробуйте изменить описание."
                )
            
            logger.error(f"Генерация провалилась. Причина: {finish_reason}. Промпт: {enhanced_prompt}")
            await message.answer(error_message)


    except APIError as e:
        logger.error(f"Ошибка Gemini API: {e}")
        await message.answer(f"❌ **Ошибка Gemini API:** Произошла ошибка связи с сервисом.\n"
                             f"Детали: `{e}`")
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await message.answer(f"❌ **Критическая ошибка:** Что-то пошло не так при обработке запроса. `{e}`")
    finally:
        # Удаление сообщения о статусе после завершения работы
        try:
             await bot.delete_message(chat_id=status_message.chat.id, message_id=status_message.message_id)
        except Exception:
             pass 

@dp.message()
async def handle_text(message: types.Message):
    """Отправляет подсказку, если пользователь ввел обычный текст без команды."""
    await message.answer(
        "Пожалуйста, используйте команду `/photo` для генерации изображения.\n"
        "Например: `/photo Космонавт в поле подсолнухов`"
    )

# --- Настройка Вебхука и Запуск ---

async def set_telegram_webhook():
    """Устанавливает вебхук на URL хостинга (Render)."""
    # Если переменная RENDER_EXTERNAL_URL не установлена, запускаем в режиме long-polling
    if not WEBHOOK_HOST:
        logger.error("Переменная RENDER_EXTERNAL_URL не найдена. Запуск в режиме long-polling.")
        await dp.start_polling(bot)
        return
        
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен, невозможно установить вебхук.")
        return

    logger.info(f"Установка вебхука на: {WEBHOOK_URL}")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=TELEGRAM_BOT_TOKEN 
    )
    logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")

async def main():
    """Основная точка входа в приложение."""
    
    # 1. Настройка вебхука (или запуск long-polling)
    await set_telegram_webhook()
    
    # Если мы в режиме long-polling, то дальнейший код aiohttp не нужен
    if not WEBHOOK_HOST:
        return

    # 2. Запуск aiohttp сервера для обработки вебхуков
    
    async def webhook_handler(request: web.Request):
        """Обрабатывает входящие POST-запросы от Telegram."""
        # Проверка секретного токена
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_BOT_TOKEN:
             return web.Response(status=403, text="Invalid secret token")
        
        # Передача обновления диспетчеру aiogram
        update = types.Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot, update)
        return web.Response(text="OK")

    async def health_check_handler(request: web.Request):
        """Хэндлер для проверки работоспособности сервиса."""
        return web.Response(status=200, text="Service is healthy")

    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    app.router.add_get("/", health_check_handler) 
    app.router.add_head("/", health_check_handler)

    # Порт, который предоставляет хостинг (например, Render)
    port = int(os.getenv("PORT", 8080)) 
    logger.info(f"Запуск веб-сервера на порту: {port}")
    
    # Настройка и запуск aiohttp
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    # Бесконечный цикл для поддержания работы
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}")
