# Correr la app desde tu propia conexión (Windows)

Corriendo la app en **tu PC**, Google ve tu internet de casa y confía en el
navegador: el **"No soy un robot" pasa casi siempre de un clic y sin fotos**.
Es la forma legítima de acercarse a lo "instantáneo". La app guarda las cookies
en tu PC (perfil persistente), así que cada vez confía más.

---

## Paso 1 — Instalar Docker Desktop (una sola vez)

1. Descarga **Docker Desktop** para Windows: https://www.docker.com/products/docker-desktop/
2. Instálalo (siguiente, siguiente) y **reinicia el PC** si te lo pide.
3. Abre Docker Desktop y espera a que diga **"Engine running"** (abajo a la izquierda, en verde).

> Solo se hace una vez. Después ya queda listo.

---

## Paso 2 — Descargar la app

Opción fácil, sin Git:

1. Entra a https://github.com/jjospinagon/antecedentes-app
2. Botón verde **Code** → **Download ZIP**.
3. Descomprime el ZIP en una carpeta, por ejemplo `C:\antecedentes-app`.

---

## Paso 3 — Encenderla

Doble clic en el archivo **`iniciar.bat`** que está dentro de la carpeta.

- La primera vez tarda unos **5–10 minutos** (arma todo). Las siguientes, segundos.
- Cuando veas en la ventana negra líneas que dicen `Uvicorn running on ...`, ya está encendida.
- **Deja esa ventana abierta** mientras uses la app. Para apagarla, ciérrala.

---

## Paso 4 — Abrirla desde el computador o el celular

**En el mismo PC:** abre el navegador en http://localhost:8000

**Desde el celular** (tiene que estar en el **mismo wifi** que el PC):

1. En el PC, abre el menú Inicio, escribe `cmd` y ábrelo.
2. Escribe `ipconfig` y presiona Enter.
3. Busca **"Dirección IPv4"** — algo como `192.168.1.15`.
4. En el celular, abre el navegador y entra a `http://192.168.1.15:8000`
   (reemplaza por tu número). Guárdalo en favoritos.

> Nota: desde el celular por IP local no se puede "Agregar a pantalla de inicio"
> como app (los navegadores lo bloquean sin https), pero funciona igual como
> página web. En el PC sí queda como app.

---

## ¿Y el captcha?

- La primera consulta quizás te pida el clic del "No soy un robot", y tal vez
  una vez las fotos. De ahí en adelante, como el perfil ya quedó reconocido,
  normalmente **pasa de un solo clic**.
- Si algún portal se pone terco igual, usa el botón **"El captcha no cede:
  abrir este portal en mi navegador"** y adjunta el PDF. Nunca te quedas sin él.

---

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `docker` no se reconoce | Docker Desktop no está abierto o no terminó de instalar. Ábrelo y espera el "Engine running". |
| El celular no abre la página | ¿Están los dos en el mismo wifi? ¿Escribiste bien la IPv4 y `:8000`? |
| La ventana se cierra sola | Falta Docker Desktop corriendo. Ábrelo primero, luego `iniciar.bat`. |
| Quiero borrar la reputación guardada | Borra la carpeta `datos` que aparece dentro de la app. |

---

## Alternativa: seguir usando la versión en la nube

Si no quieres instalar nada, la app sigue viva en
**https://antecedentes.onrender.com** — pero al correr en un servidor, algunos
portales te pondrán fotos. Correrla desde tu PC es lo que las evita.
