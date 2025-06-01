﻿FROM python:3.11-slim

WORKDIR /app

# ��⠭�������� ��⥬�� ����ᨬ���
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# �����㥬 requirements � ��⠭�������� ����ᨬ���
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# �����㥬 ��� �ਫ������
COPY . .

# ������� ��४��� ��� �����
RUN mkdir -p logs

# ������� ���ਢ�����஢������ ���짮��⥫�
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

CMD ["python", "main.py"]
