# Certificados de Antecedentes — app web/móvil

Genera en **un solo PDF** los certificados de:

| Certificado | Entidad | CC/CE/TI/PA | NIT |
|---|---|:--:|:--:|
| Antecedentes disciplinarios | Procuraduría General de la Nación | ✔ | ✔ |
| Antecedentes fiscales | Contraloría General de la República | ✔ | ✔ |
| Antecedentes judiciales | Policía Nacional (WebJudicial) | ✔ | — |
| Medidas correctivas (RNMC) | Policía Nacional (Ley 1801/2016) | ✔ | — |

Digitas **una sola vez** tipo de documento, número y fecha de expedición. La app
abre los cuatro portales, diligencia los formularios, te muestra cada captcha en
el celular para que **tú lo resuelvas**, envía la consulta, captura el PDF y al
final entrega un consolidado con carátula.

> **El captcha nunca se evade.** La app automatiza lo repetitivo (navegar,
> diligenciar, descargar, unir); la verificación humana la haces tú desde la
> misma pantalla. Ese es justamente el diseño que hace que funcione de forma
> estable y sin violar los términos de los portales.

---

## Arquitectura

```
Celular (PWA)                     Servidor (Docker)
┌──────────────────┐   WebSocket  ┌──────────────────────────────┐
│ formulario       │ ───────────► │ FastAPI + Playwright         │
│ visor de pantalla│ ◄─────────── │ Chromium headless (1 por      │
│ toques + teclado │   frames JPEG│ portal, contexto aislado)    │
└──────────────────┘              │ pypdf → PDF consolidado      │
        ▲                         └──────────────────────────────┘
        └── descarga del PDF final ──────────────┘
```

El navegador corre **en el servidor**, no en tu celular. Tu pantalla es un
espejo: los toques y el teclado se reenvían al navegador remoto. Por eso el
captcha se resuelve en el origen correcto y funciona con captcha de texto,
reCAPTCHA o cualquier variante que pongan mañana.

**Flujo por portal**

1. Abre y diligencia los campos → automático
2. **Pausa**: resuelves el captcha desde el celular → manual
3. Envía el formulario → automático
4. **Pausa**: verificas el resultado y pulsas *Guardar y continuar* → manual
5. Captura el PDF y pasa al siguiente portal → automático

El paso 4 se puede desactivar con `REVISION_MANUAL=0` (queda 100% automático
después del captcha).

---

## Despliegue (lo que tienes que hacer una vez)

### 1. Subir el repo a GitHub

```bash
cd antecedentes-app
git init && git add . && git commit -m "App certificados de antecedentes"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/antecedentes-app.git
git push -u origin main
```

### 2. Desplegar en Render

1. Entra a <https://dashboard.render.com> → **New** → **Blueprint**
2. Conecta el repositorio → Render detecta `render.yaml` → **Apply**
3. A los ~5 min tienes una URL tipo `https://antecedentes.onrender.com`

El plan `free` sirve, pero se duerme tras 15 min sin uso (la primera consulta
tarda ~40 s en despertar). El plan `starter` (7 USD/mes) evita eso; se cambia
en `render.yaml` → `plan:`.

**Alternativas** con el mismo `Dockerfile`: Google Cloud Run (escala a cero,
capa gratuita generosa), Fly.io, Railway o cualquier VPS con Docker.

### 3. Instalarla en el celular

Abre la URL en Chrome (Android) o Safari (iOS) → menú → **Agregar a pantalla de
inicio**. Queda como app nativa, en pantalla completa.

---

## Uso local (para probar o ajustar)

```bash
docker compose up --build        # http://localhost:8000
```

o sin Docker:

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
uvicorn app.main:app --reload
```

### Modo de prueba sin tocar los portales del Estado

```bash
PORTAL_DEMO=1 uvicorn app.main:app
```

Agrega un portal simulado local para verificar que todo el circuito funciona
(streaming, toques, captcha, PDF). Su captcha de prueba es `7K4M9`.

### Pruebas automatizadas

```bash
python3 tests/e2e_demo.py    # motor: pausa humana, clic/teclado remoto, PDF
python3 tests/e2e_ws.py      # servidor completo: HTTP + WebSocket + PWA
```

---

## Variables de entorno

| Variable | Def. | Para qué |
|---|---|---|
| `REVISION_MANUAL` | `1` | Pausa de verificación del resultado antes de capturar |
| `FPS_STREAM` | `1.6` | Cuadros por segundo del espejo de pantalla |
| `ESPERA_MAX_HUMANO_S` | `600` | Tiempo máximo esperando tu captcha |
| `TTL_SESION_S` | `1800` | Vida del PDF en memoria antes de purgarse |
| `PORTAL_DEMO` | — | `1` activa el portal simulado |
| `PORT` | `8000` | Puerto del servidor |

---

## Cuando un portal cambie de maquetación

Pasa seguido. La app **no se rompe**: si no encuentra un campo lo dice en la
bitácora (`AVISO: no se ubico ...`) y te deja diligenciarlo con el dedo sobre la
pantalla espejo. Para volver a automatizarlo:

1. Abre la app, corre el portal y mira la **Bitácora técnica** al pie
2. Identifica el campo que quedó sin ubicar
3. Agrega el nuevo selector **al inicio de la lista** en
   `app/portales/<portal>.py`

```python
await escribir(
    page,
    ["#nuevoIdDelCampo",   # ← nuevo, va primero
     "#txtNumID", "input[name*='NumID']"],
    datos.numero, log, "numero de documento",
)
```

Las listas se prueban en orden y el primero visible gana, así que nunca hay que
borrar los selectores viejos. Un cambio de portal es una línea.

---

## Estructura

```
app/
  main.py            API REST + WebSocket + servidor de la PWA
  sesion.py          motor: orquestación, pausa humana, streaming
  config.py          parámetros (viewport, fps, timeouts)
  pdf.py             carátula + consolidación con pypdf
  portales/
    base.py          contrato + helpers tolerantes + CazadorPDF
    procuraduria.py  contraloria.py  policia.py  rnmc.py  demo.py
web/                 PWA (HTML + CSS + JS, sin frameworks)
tests/               pruebas de extremo a extremo
Dockerfile  render.yaml  docker-compose.yml
```

`CazadorPDF` intercepta el certificado por las tres vías posibles: descarga
directa, respuesta HTTP `application/pdf` o pestaña emergente. Si el portal solo
muestra HTML (caso Policía y RNMC), imprime la página a PDF.

---

## Notas de uso responsable

- Los cuatro portales son de consulta pública y gratuita. La app no evade
  controles de seguridad: reproduce la consulta manual y tú resuelves el captcha.
- Si consultas antecedentes de terceros (personal de obra, proponentes,
  subcontratistas), estás tratando datos personales: aplica la **Ley 1581 de
  2012** (autorización previa, finalidad determinada, custodia y supresión).
  Conviene dejar la autorización firmada en la carpeta del contrato.
- La validez jurídica de cada certificado la da el **código de verificación** de
  la entidad emisora, no este consolidado. La carátula lo advierte de forma
  expresa.
- No abuses de la frecuencia de consulta: los portales limitan por IP y una IP
  compartida (Render) puede quedar bloqueada temporalmente.
