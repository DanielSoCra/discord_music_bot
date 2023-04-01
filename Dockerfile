FROM python:3.9

WORKDIR /app

RUN apt-get update && \
    apt-get install -y libopus0 && \
    apt-get install -y ffmpeg

RUN apt-get update && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir -r requirements.txt
RUN python3 -m pip install -U discord.py[voice]

COPY . .

CMD ["python", "main.py"]
