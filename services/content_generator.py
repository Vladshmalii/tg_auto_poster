from typing import Dict
from services.news_service import NewsItem
import re
import logging


class ContentGenerator:

    def __init__(self):
        self.style_templates = {
            'formal': {
                'prefix': '📰 <b>News</b>\n\n',
                'title_format': '<b>{title}</b>\n\n',
                'description_format': '{description}\n\n',
                'link_format': '🔗 <a href="{url}">Read more</a>',
                'footer': '\n\n📊 #news #{category}'
            },
            'casual': {
                'prefix': '👋 Hey! Fresh news:\n\n',
                'title_format': '🔥 <b>{title}</b>\n\n',
                'description_format': '{description}\n\n',
                'link_format': '👀 <a href="{url}">Read here</a>',
                'footer': '\n\n✌️ See you! #{category}'
            },
            'meme': {
                'prefix': '🤡 ATTENTION! IMPORTANT INFO!\n\n',
                'title_format': '💥 {title} 💥\n\n',
                'description_format': '😎 {description}\n\n',
                'link_format': '🤓 <a href="{url}">Click here, smarty</a>',
                'footer': '\n\n🔥🔥🔥 #fire #content #{category}'
            }
        }

    async def generate_post(self, news_item: NewsItem, style: str = 'formal', category: str = 'news') -> str:
        try:
            template = self.style_templates.get(style, self.style_templates['formal'])

            clean_description = self._clean_html(news_item.description)

            if len(clean_description) > 800:
                clean_description = clean_description[:797] + '...'

            post_content = template['prefix']
            post_content += template['title_format'].format(title=news_item.title)

            if clean_description:
                post_content += template['description_format'].format(description=clean_description)

            post_content += template['link_format'].format(url=news_item.url)
            post_content += template['footer'].format(category=category)

            if len(post_content) > 4000:
                max_desc_length = 4000 - len(post_content) + len(clean_description)
                if max_desc_length > 100:
                    clean_description = clean_description[:max_desc_length - 3] + '...'
                    post_content = template['prefix']
                    post_content += template['title_format'].format(title=news_item.title)
                    post_content += template['description_format'].format(description=clean_description)
                    post_content += template['link_format'].format(url=news_item.url)
                    post_content += template['footer'].format(category=category)

            logging.info(f"Generated post with {len(post_content)} characters")
            return post_content

        except Exception as e:
            logging.error(f"Content generation error: {e}")
            return f"❌ Post generation error: {str(e)}"

    def _clean_html(self, text: str) -> str:
        if not text:
            return ""

        clean_text = re.sub(r'<[^>]+>', '', text)

        import html
        clean_text = html.unescape(clean_text)

        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text