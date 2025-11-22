# main.py
import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Update
from aiohttp import web # Важно! Для работы Webhook

# Импорт ваших файлов
from config import BOT_TOKEN, GEMINI_API_KEY 
from generator import GeminiGenerator 

# Настройка логирования
logging.basicConfig(level=logging.INFO)
router = Router()
gemini_gen: GeminiGenerator = None 

# --- Настройки Render Webhook ---
# Используем переменные окружения, предоставляемые Render
WEB_SERVER_HOST = '0.0.0.0'
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080)) 
WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}' 
# RENDER_EXTERNAL_URL будет установлен самой платформой
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") + WEBHOOK_PATH 

# --- FSM для сбора запроса ---

class Generation(StatesGroup):
    """Состояния для процесса генерации."""
    waiting_for_prompt_photo = State()

# --- Хендлеры Telegram ---

@router.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """Приветствие и информация о командах."""
    welcome_text = (
        f"👋 Привет, {message.from_user.full_name}!\n"
        "Я чат-бот для **генерации изображений** с помощью Google Gemini API.\n\n"
        "**Команды:**\n"
        "/photo - Начать генерацию изображения"
    )
    await message.answer(welcome_text, parse_mode='Markdown')

# --- ГЕНЕРАЦИЯ ФОТО ---

@router.message(Command("photo"))
async def start_photo_generation(message: types.Message, state: FSMContext) -> None:
    """Начинает процесс генерации фото."""
    await message.answer(
        "🖼️ Пришлите мне подробное **описание изображения** (рекомендуется на английском), "
        "которое вы хотите создать."
    )
    await state.set_state(Generation.waiting_for_prompt_photo)

@router.message(Generation.waiting_for_prompt_photo, F.text)
async def process_photo_prompt(message: types.Message, state: FSMContext) -> None:
    """Получает запрос и отправляет его в Gemini API для генерации фото."""
    await state.clear() 
    
    prompt = message.text
    # Отправляем предварительное сообщение, пока идет генерация
    await message.answer(f"⏳ Ваш запрос '{prompt}' принят. Генерирую изображение. Это может занять до 30 секунд...")

    # Вызов генератора
    image_file = await gemini_gen.generate_image(prompt)

    if image_file:
        # Отправка сгенерированного изображения
        await message.answer_photo(
            photo=image_file,
            caption=f"✅ Ваше фото готово по запросу: *{prompt}*",
            parse_mode='Markdown'
        )
    else:
        await message.answer(
            "❌ Извините, не удалось сгенерировать изображение. Проверьте лог или попробуйте другой запрос."
        )

# --- Логика Webhook AIOHTTP ---

async def handle_telegram_update(request):
    """Обработчик входящих HTTP-запросов от Telegram."""
    bot = request.app['bot']
    dp = request.app['dp']

    if request.method == 'POST':
        try:
            # Получаем объект обновления от Telegram
            update = Update.model_validate_json(await request.text())
            # Передаем его в диспетчер aiogram
            await dp.feed_update(bot, update)
            return web.Response(status=200) # Обязательно ответить 200 OK
        except Exception as e:
            logging.error(f"Ошибка обработки обновления: {e}")
            return web.Response(status=500)
    return web.Response(status=405) # Метод не разрешен (только POST)

async def on_startup(app):
    """Выполняется при запуске Web Service (устанавливает Webhook)."""
    logging.info("Инициализация генератора и установка Webhook...")
    
    global gemini_gen
    gemini_gen = GeminiGenerator(api_key=GEMINI_API_KEY)
    
    bot = app['bot']
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен на URL: {WEBHOOK_URL}")

async def on_shutdown(app):
    """Выполняется при завершении работы (удаляет Webhook)."""
    bot = app['bot']
    await bot.delete_webhook()
    logging.info("Webhook удален.")

def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router) # Регистрация вашего роутера

    # Инициализация AIOHTTP приложения
    app = web.Application()
    app['bot'] = bot
    app['dp'] = dp
    
    # Настраиваем обработчик для Webhook-пути
    app.router.add_post(WEBHOOK_PATH, handle_telegram_update)
    
    # Регистрация хуков запуска и завершения
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Запуск web-сервера
    web.run_app(
        app,
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT
    )

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.critical(f"Критическая ошибка запуска Webhook: {e}")
