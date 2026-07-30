# Chromium se instala con la misma version que el paquete pip de Playwright,
# asi nunca aparece el clasico "Executable doesn't exist" al desplegar.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /srv

COPY requirements.txt .
# xvfb + xauth: display virtual para que Chromium corra CON ventana.
# 'playwright install --with-deps' NO los trae en la imagen slim.
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium \
 && apt-get update \
 && apt-get install -y --no-install-recommends xvfb xauth \
 && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY web ./web
COPY tests ./tests

EXPOSE 8000

# HEADLESS=0 + xvfb-run: Chromium arranca con ventana sobre un display
# virtual. reCAPTCHA castiga a los navegadores sin pantalla encadenando
# retos de imagenes infinitos; con display real se comporta normal.
# (xvfb ya viene instalado por 'playwright install --with-deps'.)
ENV HEADLESS=0
ENV DISPLAY=:99
# Se arranca Xvfb directo en vez de 'xvfb-run': este ultimo depende de xauth y
# falla con "status 3" si falta. Un solo worker: las sesiones de navegador
# viven en memoria del proceso.
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x1000x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 2; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 75"]
