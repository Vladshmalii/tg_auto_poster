# Telegram Auto Poster Bot

## Description

This project is a Telegram bot for automatic posting and content management in channels. The bot supports:
- Automatic scheduled posting (Celery + Redis)
- Manual and delayed posting
- User subscription management
- Integration with external services (e.g., OpenAI, CryptoBot)
- Analytics and data backup
- Flexible configuration via environment variables

## Main Technologies
- Python 3.11
- [aiogram 3](https://docs.aiogram.dev/en/latest/) — Telegram Bot API
- Celery — task queue and periodic jobs
- Redis — queue broker and state storage
- SQLAlchemy, asyncpg — async PostgreSQL support
- Docker/Docker Compose — containerization
- FastAPI

## Project Structure
```
pet_tg_bot/
├── bot/                # Bot logic, handlers, keyboards
├── services/           # Services for autoposting, content generation, etc.
├── database/           # Models and DB logic
├── config/             # Configuration and environment variables
├── tasks.py            # Celery tasks
├── celery_app.py       # Celery setup
├── main.py             # Entry point, bot launch
├── requirements.txt    # Dependencies
├── Dockerfile          # Docker image
├── docker-compose.yml  # Docker Compose
```

## Quick Start

### 1. Clone and Install Dependencies
```bash
# Clone repository
 git clone <this_repository>
 cd pet_tg_bot

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file using `.env.example` as a template and set:
- BOT_TOKEN — Telegram bot token
- DATABASE_URL — PostgreSQL connection string
- REDIS_URL — Redis connection string
- ADMIN_IDS — admin user IDs (comma-separated)
- OPENAI_API_KEY, CRYPTOBOT_TOKEN — if needed

### 3. Apply Database Migrations
```bash
alembic upgrade head
```

### 4. Run
- **Bot:**
    ```bash
    python main.py
    ```
- **Celery worker:**
    ```bash
    celery -A celery_app.celery_app worker --loglevel=info
    ```
- **Celery beat (scheduler):**
    ```bash
    celery -A celery_app.celery_app beat --loglevel=info
    ```
- **Docker (recommended):**
    ```bash
    docker-compose up --build
    ```

## Example Environment Variables
```
BOT_TOKEN=...            # Telegram bot token
DATABASE_URL=postgresql://user:pass@localhost/telegram_bot
REDIS_URL=redis://localhost:6379/0
ADMIN_IDS=123456789,987654321
OPENAI_API_KEY=...
CRYPTOBOT_TOKEN=...
```

## Main Features
- Automatic and manual posting
- Flexible scheduling
- Subscriptions and tariffs
- Integration with external APIs
- Backup and analytics
- Modular and extendable architecture

## Architecture
- `main.py` — bot launch, router registration
- `tasks.py` — Celery tasks for posting, analytics, subscriptions, backups
- `services/` — business logic (autoposting, content generation, etc.)
- `database/` — models, migrations, sessions
- `config/settings.py` — dataclass-based config (env + defaults)

## Note
This project is created for portfolio purposes.
