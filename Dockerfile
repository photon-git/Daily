FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libreoffice \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD uvicorn webhook:app --host 0.0.0.0 --port $PORT & streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true & wait
