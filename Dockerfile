FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/interactive-text-analysis/matplotlib \
    HF_HOME=/tmp/interactive-text-analysis/huggingface

WORKDIR /app

RUN mkdir -p /tmp/interactive-text-analysis/matplotlib /tmp/interactive-text-analysis/huggingface

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

