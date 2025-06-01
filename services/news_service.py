import aiohttp
import feedparser
import random
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging


@dataclass
class NewsItem:
    title: str
    description: str
    url: str
    image_url: Optional[str] = None
    published_at: Optional[str] = None


class NewsService:
    """Сервис для получения новостей из различных источников"""

    def __init__(self):
        self.sources = {
            'it': [
                'https://dou.ua/rss/articles',
                'https://itc.ua/feed/',
                'https://ain.ua/feed/',
                'https://dev.ua/rss',
                'https://techcrunch.com/feed/',
            ],
            'crypto': [
                'https://forklog.com/feed/',
                'https://cryptonews.net/ua/rss/',
                'https://cointelegraph.com/rss',
                'https://coindesk.com/arc/outboundfeeds/rss/',
                'https://decrypt.co/feed',
            ],
            'business': [
                'https://delo.ua/rss/',
                'https://nv.ua/rss/business.rss',
                'https://lb.ua/rss',
                'https://mind.ua/rss',
                'https://biz.liga.net/rss.xml',
            ],
            'general': [
                'https://www.pravda.com.ua/rss/',
                'https://nv.ua/rss/all.rss',
                'https://www.unian.ua/rss',
                'https://tsn.ua/rss/full.rss',
                'https://24tv.ua/rss/all.rss',
                'https://suspilne.media/rss',
            ],
            'esports': [
                'https://cybersport.ua/rss/',
                'https://esports.com.ua/feed/',
                'https://dotesports.com/feed',
                'https://www.dexerto.com/feed/',
                'https://win.gg/feed/',
            ],
            'tech': [
                'https://itc.ua/feed/',
                'https://techno.nv.ua/rss.xml',
                'https://gagadget.com/feed/',
                'https://root-nation.com/feed/',
                'https://tech.liga.net/rss.xml',
            ],
            'politics': [
                'https://www.pravda.com.ua/rss/view_news/',
                'https://nv.ua/rss/politics.rss',
                'https://www.radiosvoboda.org/api/epiqq',
                'https://hromadske.ua/rss',
                'https://detector.media/rss',
            ],
            'science': [
                'https://hi-tech.ua/feed/',
                'https://naukatehnika.com/feed/',
                'https://nplus1.ru/rss',
                'https://techcrunch.com/category/science/feed/',
                'https://www.space.com/feeds/all',
            ],
            'auto': [
                'https://auto.liga.net/rss.xml',
                'https://autocentre.ua/rss/',
                'https://kolesa.ua/rss/news/',
                'https://autoblog.com.ua/feed/',
                'https://motor.ru/rss/news.xml',
            ],
            'health': [
                'https://24tv.ua/rss/health.rss',
                'https://tsn.ua/rss/zdorovya.rss',
                'https://nv.ua/rss/health.rss',
                'https://www.health.com/rss/news',
                'https://medlineplus.gov/rss/healthnews.xml',
            ],
            'entertainment': [
                'https://24tv.ua/rss/showbiz.rss',
                'https://showbiz.ua/rss/',
                'https://vogue.ua/rss',
                'https://elle.ua/rss/',
                'https://variety.com/feed/',
            ],
            'sport': [
                'https://sport.ua/rss',
                'https://terrikon.ck.ua/rss/all',
                'https://football24.ua/rss/',
                'https://champion.gg/feed/',
                'https://espn.com/espn/rss/news',
            ]
        }

    async def get_random_news(self, category: str) -> Optional[NewsItem]:
        """Получает случайную новость по категории"""
        try:
            sources = self.sources.get(category, [])
            if not sources:
                logging.warning(f"Нет источников для категории: {category}")
                return None

            # Пробуем несколько источников
            for source_url in sources:
                try:
                    logging.info(f"Пытаемся получить новости из: {source_url}")

                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(source_url) as response:
                            if response.status == 200:
                                rss_content = await response.text()
                                feed = feedparser.parse(rss_content)

                                if feed.entries:
                                    # Выбираем случайную новость из первых 10
                                    entry = random.choice(feed.entries[:10])

                                    # Очищаем описание от HTML
                                    description = self._clean_html(entry.get('summary', ''))

                                    news_item = NewsItem(
                                        title=entry.title,
                                        description=description,
                                        url=entry.link,
                                        published_at=entry.get('published', '')
                                    )

                                    logging.info(f"Получена новость: {news_item.title[:50]}...")
                                    return news_item
                                else:
                                    logging.warning(f"Нет записей в RSS: {source_url}")
                            else:
                                logging.warning(f"Ошибка HTTP {response.status}: {source_url}")

                except Exception as e:
                    logging.error(f"Ошибка получения новостей из {source_url}: {e}")
                    continue

            logging.error(f"Не удалось получить новости ни из одного источника для категории: {category}")
            return None

        except Exception as e:
            logging.error(f"Общая ошибка получения новостей: {e}")
            return None

    def _clean_html(self, text: str) -> str:
        """Очищает текст от HTML тегов"""
        if not text:
            return ""

        import re
        # Удаляем HTML теги
        clean_text = re.sub(r'<[^>]+>', '', text)
        # Убираем лишние пробелы и переносы
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text