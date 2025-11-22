import asyncio
import logging
import os
import io
import base64
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import BufferedInputFile
from aiogram.filters.command import Command
from aiohttp import web
from PIL import Image

from google import genai
from google.genai import types
from google.genai.errors import APIError

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Загрузка переменных окружения и константы ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") # Например: https://your-render-service.onrender.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", f"/webhook/{os.getenv('TG_WEBHOOK_SECRET')}")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEB_SERVER_HOST = '0.0.0.0'
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# --- Настройка моделей Gemini/Veo ---
TEXT_MODEL = "gemini-2.5-flash-preview-09-2025"          # Для улучшения промптов
VEO_MODEL = "veo-3.1-generate-preview"                  # Для генерации видео

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY or not WEBHOOK_HOST:
    logger.error("❌ Отсутствуют необходимые переменные окружения (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, WEBHOOK_HOST).")
    exit()

# --- Инициализация клиентов ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    logger.info("✅ Генератор Gemini инициализирован.")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации Gemini клиента: {e}")
    exit()


# --- Вспомогательные функции ---

async def enhance_prompt(prompt: str) -> str:
    """Улучшает короткий пользовательский промпт, добавляя детали для лучшей генерации видео."""
    # Используется только для текстового промпта, чтобы сделать его более детализированным
    system_instruction = (
        "Ты — креативный директор по цифровому искусству. Твоя задача — "
        "превратить короткий, простой запрос пользователя (промпт) в детальное, "
        "высококачественное описание движения, стиля и атмосферы для генерации видео. "
        "Отвечай ТОЛЬКО улучшенным промптом, без лишних слов."
    )
    
    try:
        response = gemini_client.models.generate_content(
            model=TEXT_MODEL,
            contents=[prompt],
            system_instruction=types.SystemInstruction(parts=[types.Part.from_text(system_instruction)]),
        )
        enhanced_prompt = response.text.strip().replace('"', '')
        logger.info(f"Улучшенный промпт: {enhanced_prompt}")
        return enhanced_prompt
    except APIError as e:
        logger.error(f"Ошибка API при улучшении промпта: {e}")
        return prompt # Возвращаем оригинальный промпт в случае ошибки


# --- Рабочий процесс Veo (Фоновая задача) ---

async def veo_video_worker(chat_id: int, enhanced_prompt: str, status_message: types.Message, image_input_data: dict = None):
    """
    Универсальная фоновая задача для обработки LRO генерации видео Veo.
    Принимает опциональные Base64-данные изображения (если это режим 'Изображение в Видео').
    """
    try:
        # 1. Запуск генерации видео
        
        generate_args = {
            "model": VEO_MODEL,
            "prompt": enhanced_prompt,
            "config": types.GenerateVideosConfig(aspect_ratio="16:9") # Задаем соотношение сторон
        }
        
        # Если предоставлено входное изображение, добавляем его в аргументы
        if image_input_data is not None:
            generate_args["image"] = image_input_data
        
        operation = gemini_client.models.generate_videos(**generate_args)
        operation_name = operation.name
        
        logger.info(f"Операция Veo LRO запущена: {operation_name}")

        # 2. Опрос LRO до завершения (шаг 2/2 или 3/3)
        while not operation.done:
            await asyncio.sleep(10) # Опрос каждые 10 секунд
            operation = gemini_client.operations.get(operation_name)
            logger.info(f"Статус LRO {operation_name}: {operation.metadata.state.name}")
        
        # 3. Обработка и отправка результата
        video_part = operation.response.generated_videos[0].video.inline_data

        if video_part and video_part.data:
            video_bytes = base64.b64decode(video_part.data)
            
            await bot.send_video(
                chat_id=chat_id,
                video=BufferedInputFile(video_bytes, filename="generated_video.mp4"),
                caption=f"🎥 **Готово!** Видео сгенерировано с помощью Veo 3.1.\n\n"
                        f"_Использованный промпт:_\n`{enhanced_prompt}`",
                parse_mode="Markdown"
            )
        else:
             await bot.send_message(
                chat_id=chat_id, 
                text="❌ **Ошибка генерации видео:** Не удалось получить данные видео из ответа Veo."
            )

    except APIError as e:
        logger.error(f"Ошибка API Gemini/Veo в воркере: {e}")
        await bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **Ошибка API при генерации видео:** Произошла ошибка связи с сервисом. Детали: `{e}`"
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка в воркере Veo: {e}", exc_info=True)
        await bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **Критическая ошибка:** Что-то пошло не так при обработке запроса видео: {type(e).__name__}."
        )
    finally:
        # Удаление сообщения о загрузке/статусе
        try:
             await bot.delete_message(chat_id=status_message.chat.id, message_id=status_message.message_id)
        except Exception:
             pass 


# --- Обработчики Telegram ---

@dp.message(Command("start"))
async def handle_start(message: types.Message):
    """Отправляет приветственное сообщение."""
    await message.answer(
        "👋 Привет! Я бот-генератор видео на базе Veo. "
        "У меня есть два режима работы:\n\n"
        "1. **Генерация с нуля (Текст в Видео)**:\n"
        "   Используйте: `/video [описание сцены и движения]`\n"
        "   _(Veo сам сгенерирует исходный кадр)._\n\n"
        "2. **Ваше фото в Видео (Изображение в Видео)**:\n"
        "   **Загрузите фото** с подписью, начинающейся с `#veo [промпт движения]`.\n"
        "   _(Пример подписи: `#veo Плавное панорамирование камеры влево, с легким ветерком`)"
    )

@dp.message(Command("video"))
async def handle_veo_prompt(message: types.Message):
    """Обрабатывает команду /video (Генерация с нуля: Прямой вызов Veo Text-to-Video, 2 шага)."""
    user_prompt = message.text[len('/video'):].strip()
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not user_prompt:
        await message.answer("❌ **Ошибка:** Пожалуйста, укажите описание для видео после команды `/video`.\n"
                             "Пример: `/video Плавный широкий кадр котенка, спящего на солнышке`")
        return

    logger.info(f"Получен промпт для видео (Текст в Видео): {user_prompt} от пользователя {user_id}")
    
    status_message = await message.answer(
        f"🎥 **Текст в Видео** запущена!\n"
        "Это займет от **1 до 5 минут**.\n"
        "🤖 0/2: Инициализация и улучшение промпта...",
        parse_mode="Markdown"
    )

    try:
        # 1. Улучшение промпта (Шаг 0/2)
        enhanced_prompt = await enhance_prompt(user_prompt)
        
        # 2. Запуск Veo (Шаг 1/2)
        await bot.edit_message_text(
            chat_id=chat_id, 
            message_id=status_message.message_id, 
            text=f"🤖 1/2: Запускаю генерацию видео с {VEO_MODEL}. Ожидайте уведомления (может занять 1-5 минут)..."
        )
        
        # 3. Запуск общего рабочего процесса Veo (без входного изображения)
        await veo_video_worker(chat_id, enhanced_prompt, status_message, image_input_data=None)

    except Exception as e:
        logger.error(f"Ошибка в процессе 'Текст в Видео': {e}", exc_info=True)
        await bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **Критическая ошибка:** Ошибка при обработке запроса: {type(e).__name__}."
        )


@dp.message(F.photo)
async def handle_user_photo(message: types.Message, bot: Bot):
    """Обрабатывает загруженные пользователем фотографии (Изображение в Видео, 3 шага)."""
    caption = message.caption or ""
    
    if not caption.lower().startswith('#veo'):
        # Игнорируем фото без соответствующей подписи
        return

    user_prompt = caption[caption.lower().find('#veo') + len('#veo'):].strip()
    
    if not user_prompt:
        await message.answer("❌ **Ошибка:** Пожалуйста, укажите промпт движения после `#veo` в подписи к фото.")
        return

    chat_id = message.chat.id
    photo = message.photo[-1] # Получаем самое крупное фото
    
    logger.info(f"Получен промпт для видео (Изображение в Видео): {user_prompt} от пользователя {message.from_user.id}")

    status_message = await message.answer(
        f"🎥 **Ваше Фото в Видео** запущена!\n"
        "Это займет от **1 до 5 минут**.\n"
        "🤖 0/3: Загружаю изображение и улучшаю промпт...",
        parse_mode="Markdown"
    )
    
    try:
        # 1. Загрузка и конвертация изображения (Шаг 0/3 - часть)
        file_info = await bot.get_file(photo.file_id)
        image_stream = io.BytesIO()
        await bot.download_file(file_info.file_path, image_stream)
        image_stream.seek(0)
        
        # Конвертация в Base64
        image_base64 = base64.b64encode(image_stream.read()).decode('utf-8')

        image_input_data = {
            "inlineData": {
                "data": image_base64,
                "mimeType": "image/jpeg" # Предполагаем, что Telegram отправляет JPEG
            }
        }
        
        # 2. Улучшение промпта движения (Шаг 1/3)
        await bot.edit_message_text(
            chat_id=chat_id, 
            message_id=status_message.message_id, 
            text=f"🤖 1/3: Улучшаю промпт движения: *{user_prompt}*...",
            parse_mode="Markdown"
        )
        enhanced_prompt = await enhance_prompt(user_prompt)
        
        # 3. Запуск Veo (Шаг 2/3)
        await bot.edit_message_text(
            chat_id=chat_id, 
            message_id=status_message.message_id, 
            text=f"🤖 2/3: Запускаю генерацию видео с {VEO_MODEL}. Ожидайте уведомления (может занять 1-5 минут)..."
        )
        
        # 4. Запуск общего рабочего процесса Veo с пользовательским изображением
        await veo_video_worker(chat_id, enhanced_prompt, status_message, image_input_data=image_input_data)

    except Exception as e:
        logger.error(f"Ошибка в процессе 'Изображение в Видео': {e}", exc_info=True)
        await bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **Критическая ошибка:** Ошибка при обработке изображения или генерации видео: {type(e).__name__}. "
            "Пожалуйста, убедитесь, что вы загрузили стандартное изображение."
        )


# --- Настройка вебхука AIOHTTP ---

async def on_startup(app):
    """Устанавливает вебхук при запуске приложения."""
    try:
        await bot.delete_webhook()
        logger.info(f"Установка вебхука на: {WEBHOOK_URL}")
        await bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"❌ Ошибка при установке вебхука: {e}")

async def on_shutdown(app):
    """Удаляет вебхук при остановке приложения."""
    logger.info("Удаление вебхука...")
    await bot.delete_webhook()
    logger.info("✅ Вебхук удален.")

async def handle_webhook(request):
    """Обрабатывает входящие обновления от Telegram."""
    logger.info(f"Получен POST-запрос на {request.path}.")
    if request.match_info.get('path') == WEBHOOK_PATH:
        try:
            update_data = await request.json()
            telegram_update = types.Update(**update_data)
            
            await dp.feed_update(bot, telegram_update)
            logger.info("Обновление обработано успешно.")
            return web.Response()
        except Exception as e:
            logger.error(f"Ошибка обработки обновления: {e}", exc_info=True)
            return web.Response(status=200) # Возвращаем 200, чтобы не было повторных попыток
    
    return web.Response(text="OK", status=200)

async def main():
    """Главная функция для запуска веб-сервера."""
    
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    
    logger.info(f"Запуск веб-сервера на порту: {WEB_SERVER_PORT}")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    await site.start()
    
    logger.info("✅ Приложение успешно запущено и ожидает запросов от Telegram.")
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        # Убедитесь, что Telegram бот не запускается в режиме Long Polling
        if WEBHOOK_HOST: 
            asyncio.run(main())
        else:
            logger.error("Для запуска в режиме вебхука необходимо установить WEBHOOK_HOST.")
    except KeyboardInterrupt:
        logger.info("Приложение остановлено вручную.")
