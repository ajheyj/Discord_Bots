FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py ocr.py store.py admin_commands.py audit_channel.py ./
RUN useradd -m bot && mkdir /app/data && chown bot:bot /app/data
USER bot
CMD ["python", "bot.py"]
