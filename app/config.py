"""Configuracion central de la aplicacion."""
import os

# --- Navegador remoto ---------------------------------------------------
# Viewport tipo movil: la captura se ve completa en el celular sin zoom.
VIEWPORT = {"width": 430, "height": 860}
DEVICE_SCALE = 2            # el JPEG sale al doble de resolucion: deja hacer
                           # zoom hasta 2x en el celular sin verse borroso.
# Calidad alta: los retos de imagen de reCAPTCHA ("selecciona los autobuses")
# son ilegibles por debajo de ~75. Y a pocos fps no alcanzas a ver que casillas
# quedaron marcadas, asi que terminas des-seleccionando. El streaming solo
# ocurre mientras TU resuelves el captcha, asi que se puede ser generoso.
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "82"))
FPS_STREAM = float(os.getenv("FPS_STREAM", "5.0"))

# --- Tiempos ------------------------------------------------------------
TIMEOUT_NAV_MS = int(os.getenv("TIMEOUT_NAV_MS", "60000"))
TIMEOUT_ACCION_MS = 15000
ESPERA_MAX_HUMANO_S = int(os.getenv("ESPERA_MAX_HUMANO_S", "600"))   # 10 min
TTL_SESION_S = int(os.getenv("TTL_SESION_S", "1800"))                # 30 min

# --- Comportamiento -----------------------------------------------------
# Si True, tras enviar el formulario la app te muestra el resultado y espera
# que pulses "Capturar" antes de generar el PDF. Es lo mas robusto frente a
# cambios de los portales.
REVISION_MANUAL = os.getenv("REVISION_MANUAL", "1") == "1"

# --- Navegador con pantalla real ----------------------------------------
# Con HEADLESS=0 el Chromium arranca en modo normal (con ventana) sobre un
# display virtual Xvfb. Es como corre un navegador de escritorio.
#
# Por que importa: reCAPTCHA le baja la puntuacion a los navegadores sin
# pantalla y responde encadenando retos de imagenes que no terminan nunca,
# aunque el humano los resuelva bien. Con pantalla real el reto se comporta
# normal. El captcha lo sigue resolviendo la persona; esto solo evita que el
# portal lo castigue por el entorno.
HEADLESS = os.getenv("HEADLESS", "1") == "1"

# --- Servidor -----------------------------------------------------------
PUERTO = int(os.getenv("PORT", "8000"))
ORIGENES_CORS = os.getenv("ORIGENES_CORS", "*").split(",")
