FROM python:3.10-slim

WORKDIR /app

# FIX: Copy all files from the build context (the mavsdk directory)
COPY . .

RUN pip install --upgrade pip && pip install -r requirements.txt

ENTRYPOINT ["python3", "telemetry_mqtt.py"]