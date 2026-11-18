
FROM python:3.10

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY . /app/

RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "bot.py"]
