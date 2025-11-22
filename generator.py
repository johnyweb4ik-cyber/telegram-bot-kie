# generator.py
import asyncio
import logging
from google import genai
from google.genai.errors import APIError
from aiogram.types import BufferedInputFile

# Настройка логирования для отладки
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class GeminiGenerator:
    """
    Класс для взаимодействия с API Gemini для генерации контента.
    
    Использует модель Imagen для создания изображений.
    """
    def __init__(self, api_key: str):
        # Инициализация клиента Google AI
        self.client = genai.Client(api_key=api_key)
        
        # Рекомендуемая модель для генерации изображений
        # NOTE: 'imagen-3.0-generate-002' может давать ошибку 404/NOT_FOUND 
        # из-за ограниченного доступа. Для стабильности вводим более старую, 
        # но общедоступную модель Imagen 2.1.
        self.image_model = 'imagen-2.1-generate-002' 
        logger.info(f"Инициализирован генератор с моделью: {self.image_model}")


    async def generate_image(self, prompt: str) -> BufferedInputFile | None:
        """
        Генерирует изображение по текстовому запросу.
        
        :param prompt: Текстовое описание изображения.
        :return: Объект BufferedInputFile, готовый к отправке в Telegram, 
                 или None в случае ошибки.
        """
        logger.info(f"Запрос генерации изображения: {prompt[:50]}...")
        try:
            # Вызов генерации изображения через правильный метод API
            result = self.client.models.generate_images(
                model=self.image_model,
                prompt=prompt,
                config=dict(
                    number_of_images=1,
                    output_mime_type="image/png", 
                    aspect_ratio="1:1"
                )
            )

            # Проверка и обработка результата
            if result.generated_images:
                image_bytes = result.generated_images[0].image.image_bytes
                logger.info("Изображение успешно сгенерировано.")
                
                # Создаем объект aiogram для отправки
                return BufferedInputFile(image_bytes, filename="generated_image.png")
            else:
                logger.warning("Ошибка: Изображение не сгенерировано. Возможно, запрос был отклонен.")
                return None
            
        except APIError as e:
            logger.error(f"Ошибка API при генерации изображения: {e}")
            return None
        except Exception as e:
            logger.critical(f"Неизвестная ошибка в GeminiGenerator: {e}")
            return None

    async def generate_video(self, prompt: str) -> str:
        """
        Концептуальная заглушка для генерации видео.
        """
        logger.info(f"Получен запрос на генерацию видео: {prompt}")
        await asyncio.sleep(3) 
        return (f"🎥 Генерация видео для запроса '{prompt}' завершена (это заглушка).")
