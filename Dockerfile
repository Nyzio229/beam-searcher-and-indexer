FROM python:3.11-slim AS base

# System deps (certy, kompilatory przydatne czasem dla wheelów)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl tini \
 && rm -rf /var/lib/apt/lists/*

# Izolacja środowiska
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Zależności
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Zasoby NLTK (EN-only)
RUN python - <<'PY'
import nltk
for pkg in ["stopwords","wordnet","omw-1.4"]:
    try:
        nltk.download(pkg, quiet=True)
    except Exception as e:
        print("NLTK download warning:", e)
PY

# Kod aplikacji
COPY indexer.py searcher.py utils.py /app/

# Dla wygody: katalog na dane użytkownika
RUN mkdir -p /data
VOLUME ["/data"]

# Domyślnie używamy Pythona jako entrypoint
ENTRYPOINT ["python"]
CMD ["-c", "print('Container ready. Use: indexer.py or searcher.py')"]