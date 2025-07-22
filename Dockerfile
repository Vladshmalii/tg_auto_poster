FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование requirements.txt
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего проекта
COPY . .

# Установка переменных окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Создание необходимых директорий
RUN mkdir -p /app/logs /app/beat /app/backups

# Установка прав
RUN chmod -R 755 /app

# Создание пользователя для безопасности (опционально)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "main.py"]