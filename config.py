# config.py
import os
# Импортируем dotenv только для локального запуска
from dotenv import load_dotenv 

load_dotenv() # Загружает локально .env

# Чтение из переменных окружения (используется Render)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
