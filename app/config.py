"""Configuracion central de la aplicacion."""
import os

# --- Navegador remoto ---------------------------------------------------
# Viewport tipo movil: la captura se ve completa en el celular sin zoom.
VIEWPORT = {"width": 430, "height": 860}
DEVICE_SCALE = 2            # captchas legibles en pantalla pequena
# Calidad alta: los retos de imagen de reCAPTCHA ("selecciona los autobuses")
# son ilegibles por debajo de ~75. Y a menos de 3 fps no alcanzas a ver que
# casillas quedaron marcadas, asi que terminas des-seleccionando.
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))
FPS_STREAM = float(os.getenv("FPS_STREAM", "3.0"))

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

# --- Servidor -----------------------------------------------------------
PUERTO = int(os.getenv("PORT", "8000"))
ORIGENES_CORS = os.getenv("ORIGENES_CORS", "*").split(",")
