from typing import Dict
from services.news_service import NewsItem
import re
import logging


class ContentGenerator:
    """Генератор контента для постов в разных стилях"""

    def __init__(self):
        self.style_templates = {
            'formal': {
                'prefix': '📰 <b>Новости</b>\n\n',
                'title_format': '<b>{title}</b>\n\n',
                'description_format': '{description}\n\n',
                'link_format': '🔗 <a href="{url}">Читать полностью</a>',
                'footer': '\n\n📊 #новости #{category}'
            },
            'casual': {
                'prefix': '👋 Привет! Свежие новости:\n\n',
                'title_format': '🔥 <b>{title}</b>\n\n',
                'description_format': '{description}\n\n',
                'link_format': '👀 <a href="{url}">Почитать тут</a>',
                'footer': '\n\n✌️ Увидимся! #{category}'
            },
            'meme': {
                'prefix': '🤡 ВНИМАНИЕ! ВАЖНАЯ ИНФА!\n\n',
                'title_format': '💥 {title} 💥\n\n',
                'description_format': '😎 {description}\n\n',
                'link_format': '🤓 <a href="{url}">Кликай сюда, умник</a>',
                'footer': '\n\n🔥🔥🔥 #огонь #контент #{category}'
            }
        }

    async def generate_post(self, news_item: NewsItem, style: str = 'formal', category: str = 'news') -> str:
        """Генерирует пост в указанном стиле"""
        try:
            template = self.style_templates.get(style, self.style_templates['formal'])

            # Очищаем описание от HTML тегов
            clean_description = self._clean_html(news_item.description)

            # Ограничиваем длину описания для Telegram
            if len(clean_description) > 800:
                clean_description = clean_description[:797] + '...'

            # Формируем пост
            post_content = template['prefix']
            post_content += template['title_format'].format(title=news_item.title)

            if clean_description:
                post_content += template['description_format'].format(description=clean_description)

            post_content += template['link_format'].format(url=news_item.url)
            post_content += template['footer'].format(category=category)

            # Проверяем длину поста (Telegram лимит 4096 символов)
            if len(post_content) > 4000:
                # Сокращаем описание
                max_desc_length = 4000 - len(post_content) + len(clean_description)
                if max_desc_length > 100:
                    clean_description = clean_description[:max_desc_length - 3] + '...'
                    post_content = template['prefix']
                    post_content += template['title_format'].format(title=news_item.title)
                    post_content += template['description_format'].format(description=clean_description)
                    post_content += template['link_format'].format(url=news_item.url)
                    post_content += template['footer'].format(category=category)

            logging.info(f"Сгенерирован пост длиной {len(post_content)} символов")
            return post_content

        except Exception as e:
            logging.error(f"Ошибка генерации контента: {e}")
            return f"❌ Ошибка генерации поста: {str(e)}"

    def _clean_html(self, text: str) -> str:
        """Очищает текст от HTML тегов"""
        if not text:
            return ""

        # Удаляем HTML теги
        clean_text = re.sub(r'<[^>]+>', '', text)

        # Декодируем HTML entities
        import html
        clean_text = html.unescape(clean_text)

        # Убираем лишние пробелы и переносы
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text