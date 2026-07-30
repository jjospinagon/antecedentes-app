/* PWA - Certificados de antecedentes ------------------------------------
   El servidor corre un navegador real; aqui solo se ve su pantalla y se le
   reenvian los toques y el teclado. El captcha lo resuelve el usuario.
------------------------------------------------------------------------ */
'use strict';

const API = location.origin;               // mismo origen que sirve la PWA
const $ = (id) => document.getElementById(id);

let ws = null, sid = null, vw = 430, vh = 860, ultimoTexto = '';
let redamSeleccionado = false;
let portalActual = null;                 // id del portal en pantalla
const PORTAL_URL = {};                   // id -> URL, para "abrir en mi navegador"
const abiertosEnNavegador = [];          // nombres que el usuario hara aparte

// Certificado que la app NO puede bajar sola porque exige cuenta personal.
// No es un portal automatizado: se descarga aparte y se adjunta al final.
const MANUALES = [{
  id: 'redam',
  nombre: 'Deudores alimentarios (REDAM)',
  entidad: 'Carpeta Ciudadana - Ley 2097/2021 (requiere tu usuario y clave)'
}];

/* --------------------------------------------------------- utilidades -- */
function pantalla(id) {
  document.querySelectorAll('.pantalla').forEach(p => p.classList.remove('activa'));
  $(id).classList.add('activa');
}
function chip(txt, clase) {
  const c = $('chipEstado');
  c.textContent = txt;
  c.className = 'chip' + (clase ? ' ' + clase : '');
}
function log(txt) {
  const p = $('log');
  p.textContent += txt + '\n';
  p.scrollTop = p.scrollHeight;
}
function enviar(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

/* ------------------------------------------------------ lista portales -- */
async function cargarPortales() {
  const cont = $('listaPortales');
  let datos = [];
  try {
    datos = await (await fetch(API + '/api/portales')).json();
  } catch (e) {
    cont.innerHTML = '<small style="color:#da3633">No hay conexion con el servidor.</small>';
    return;
  }
  cont.innerHTML = '';
  datos.forEach(p => { PORTAL_URL[p.id] = p.url; cont.appendChild(fila(p, false)); });
  MANUALES.forEach(p => cont.appendChild(fila(p, true)));
  cont.addEventListener('change', mostrarEntidad);
  cargarEntidadGuardada();
  aplicarFiltroNit();
}

function fila(p, manual) {
  const l = document.createElement('label');
  l.className = 'portal' + (manual ? ' manual' : '');
  l.dataset.nit = (p.admite_nit || manual) ? '1' : '0';
  l.dataset.manual = manual ? '1' : '0';
  l.innerHTML =
    '<input type="checkbox" value="' + p.id + '"' + (manual ? '' : ' checked') + '>' +
    '<span><b>' + p.nombre + (manual ? ' <em class="tag">adjuntar</em>' : '') +
    '</b><small>' + p.entidad + '</small></span>';
  return l;
}

function aplicarFiltroNit() {
  const esNit = $('tipoDoc').value === 'NIT';
  document.querySelectorAll('#listaPortales .portal').forEach(l => {
    const soloNatural = l.dataset.nit === '0';
    const inhabil = esNit && soloNatural;
    l.classList.toggle('inhabil', inhabil);
    const chk = l.querySelector('input');
    chk.disabled = inhabil;
    if (inhabil) chk.checked = false;
  });
  $('fecha').closest('.campo').style.display = esNit ? 'none' : '';
  mostrarEntidad();
}

// El bloque de entidad solo aparece si esta marcado delitos sexuales.
function mostrarEntidad() {
  const chk = document.querySelector('#listaPortales input[value="delitos_sexuales"]');
  $('bloqueEntidad').hidden = !(chk && chk.checked && !chk.disabled);
}

function cargarEntidadGuardada() {
  try {
    $('entidad').value = localStorage.getItem('entidad') || '';
    $('nitEntidad').value = localStorage.getItem('nitEntidad') || '';
  } catch (e) { /* modo incognito */ }
}
function guardarEntidad() {
  try {
    localStorage.setItem('entidad', $('entidad').value.trim());
    localStorage.setItem('nitEntidad', $('nitEntidad').value.trim());
  } catch (e) { /* modo incognito */ }
}

/* --------------------------------------------------------- arranque ---- */
$('tipoDoc').addEventListener('change', aplicarFiltroNit);

$('formulario').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const marcados = [...document.querySelectorAll('#listaPortales input:checked')]
    .map(i => i.value);
  const manualIds = MANUALES.map(m => m.id);
  const automaticos = marcados.filter(v => manualIds.indexOf(v) < 0);
  redamSeleccionado = marcados.indexOf('redam') >= 0;

  if (!marcados.length) { alert('Selecciona al menos un certificado.'); return; }

  if (automaticos.indexOf('delitos_sexuales') >= 0 &&
      (!$('entidad').value.trim() || !$('nitEntidad').value.trim())) {
    alert('El certificado de delitos sexuales exige la entidad que consulta y su NIT.');
    return;
  }
  guardarEntidad();

  $('btnIniciar').disabled = true;
  chip('Conectando...', 'esp');

  const cuerpo = {
    tipo_doc: $('tipoDoc').value,
    numero: $('numero').value.trim(),
    fecha_expedicion: $('fecha').value || null,
    nombre: $('nombre').value.trim() || null,
    entidad: $('entidad').value.trim() || null,
    nit_entidad: $('nitEntidad').value.trim() || null,
    portales: automaticos            // los manuales no van al backend
  };

  try {
    const r = await fetch(API + '/api/sesion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo)
    });
    if (!r.ok) throw new Error((await r.json()).detail || 'Error del servidor');
    sid = (await r.json()).sid;
    $('log').textContent = '';
    if (automaticos.length) {
      pantalla('pantallaVisor');
      abrirSocket();
    } else {
      // Solo certificados manuales: se salta el navegador y va directo a adjuntar.
      abrirSocket();                 // el backend emite 'fin' de una vez
      pantalla('pantallaVisor');
    }
  } catch (e) {
    alert('No se pudo iniciar: ' + e.message);
    chip('Error', 'err');
  } finally {
    $('btnIniciar').disabled = false;
  }
});

/* ------------------------------------------------------- websocket ----- */
function abrirSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto + '://' + location.host + '/ws/' + sid);

  ws.onopen = () => chip('En proceso', 'esp');
  ws.onclose = () => { if (!$('pantallaFin').classList.contains('activa')) chip('Desconectado', 'err'); };
  ws.onerror = () => chip('Error de conexion', 'err');

  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    switch (m.t) {
      case 'log':
        log(m.msg);
        break;

      case 'frame':
        vw = m.vw; vh = m.vh;
        $('pantalla').src = 'data:image/jpeg;base64,' + m.img;
        $('cargando').classList.add('oculto');
        break;

      case 'estado': {
        portalActual = m.portal || null;
        window._portalNombreActual = m.nombre || '';
        $('portalNombre').textContent = m.nombre || '';
        $('portalEntidad').textContent = m.entidad || '';
        $('contador').textContent = (m.idx || 0) + '/' + (m.total || 0);
        const ins = $('instruccion');
        ins.textContent = m.msg || '';
        const interactivo = (m.fase === 'captcha' || m.fase === 'revision');
        ins.classList.toggle('accion', m.fase === 'revision');
        ['btnContinuar', 'entrada', 'btnEnter', 'btnBorrar', 'btnLimpiar',
         'btnRecargar', 'btnSaltar', 'btnNavegador']
          .forEach(id => { $(id).disabled = !interactivo; });
        $('btnContinuar').textContent =
          m.fase === 'revision' ? 'Guardar y continuar' : 'Continuar';
        // Cada vez que aparece un captcha nuevo se limpia el buffer local, para
        // no arrastrar la respuesta del anterior.
        if (m.fase === 'captcha') limpiarBuffer();
        if (!interactivo) $('cargando').classList.remove('oculto');
        break;
      }

      case 'fin':
        chip('Finalizado', 'ok');
        $('cargando').classList.add('oculto');
        mostrarFin(m);
        break;

      case 'error':
        chip('Error', 'err');
        log('ERROR: ' + m.msg);
        alert('Error: ' + m.msg);
        break;
    }
  };
}

/* ============================================================ ESPEJO ====
   Toque preciso + zoom con desplazamiento. El problema con el captcha de
   imagenes era doble: (1) el toque tardaba en verse y volvias a tocar,
   deseleccionando la casilla; (2) las casillas quedaban pequenas. Se
   resuelve con: marca visual inmediata en cada toque, distincion entre
   TOCAR y ARRASTRAR (para desplazar sin marcar), y zoom 1x-3x.
======================================================================== */
const marco = $('marco');
const lienzo = $('lienzo');
const img = $('pantalla');
const capa = $('capaToques');

let zoom = 1;
const ZOOMS = [1, 1.5, 2, 3];

function aplicarZoom() {
  lienzo.style.width = (zoom * 100) + '%';
  $('zoomNivel').textContent = zoom + 'x';
}
$('btnZoomMas').onclick = () => {
  const i = ZOOMS.indexOf(zoom);
  if (i < ZOOMS.length - 1) { zoom = ZOOMS[i + 1]; aplicarZoom(); }
};
$('btnZoomMenos').onclick = () => {
  const i = ZOOMS.indexOf(zoom);
  if (i > 0) { zoom = ZOOMS[i - 1]; aplicarZoom(); }
};

function marcaToque(clientX, clientY) {
  const r = img.getBoundingClientRect();
  const punto = document.createElement('span');
  punto.className = 'ping';
  punto.style.left = (clientX - r.left) + 'px';
  punto.style.top = (clientY - r.top) + 'px';
  capa.appendChild(punto);
  setTimeout(() => punto.remove(), 550);
}

// Distinguir toque de arrastre: si el dedo se mueve poco y rapido -> toque.
let pDown = null;
img.addEventListener('pointerdown', (ev) => {
  pDown = { x: ev.clientX, y: ev.clientY, t: Date.now() };
});
img.addEventListener('pointerup', (ev) => {
  if (!pDown) return;
  const dist = Math.hypot(ev.clientX - pDown.x, ev.clientY - pDown.y);
  const dt = Date.now() - pDown.t;
  pDown = null;
  if (dist > 12 || dt > 700) return;          // fue un desplazamiento, no un toque
  const r = img.getBoundingClientRect();
  if (!r.width) return;
  const x = ((ev.clientX - r.left) / r.width) * vw;
  const y = ((ev.clientY - r.top) / r.height) * vh;
  enviar({ t: 'click', x: Math.round(x), y: Math.round(y) });
  marcaToque(ev.clientX, ev.clientY);          // feedback inmediato
  limpiarBuffer();                             // buffer nuevo por cada campo
  $('entrada').focus();
});
// Rueda del mouse (escritorio): desplaza dentro del marco.
marco.addEventListener('wheel', (ev) => {
  if (zoom > 1) return;                         // con zoom, deja el scroll nativo
  ev.preventDefault();
  enviar({ t: 'scroll', dy: ev.deltaY });
}, { passive: false });

/* ------------------------------------------------------ teclado local --
   El campo del celular es la fuente de verdad: en cada cambio se reescribe
   COMPLETO el campo remoto. Asi corregir o borrar siempre funciona y nunca
   queda pegada la respuesta anterior (el problema del captcha de letras).
------------------------------------------------------------------------ */
function limpiarBuffer() {
  ultimoTexto = '';
  $('entrada').value = '';
}
function sincronizar() {
  enviar({ t: 'reemplazar', v: $('entrada').value });
}
$('entrada').addEventListener('input', sincronizar);
$('entrada').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter') { ev.preventDefault(); enviar({ t: 'tecla', k: 'Enter' }); }
});
$('btnEnter').onclick = () => enviar({ t: 'tecla', k: 'Enter' });
$('btnBorrar').onclick = () => {
  const e = $('entrada');
  e.value = e.value.slice(0, -1);
  sincronizar();
  e.focus();
};
$('btnLimpiar').onclick = () => {
  $('entrada').value = '';
  enviar({ t: 'reemplazar', v: '' });
  $('entrada').focus();
};

/* ---------------------------------------------------------- acciones --- */
$('btnContinuar').onclick = () => {
  $('btnContinuar').disabled = true;
  $('cargando').classList.remove('oculto');
  $('entrada').value = ''; ultimoTexto = '';
  zoom = 1; aplicarZoom();
  enviar({ t: 'continuar' });
};
$('btnSaltar').onclick = () => enviar({ t: 'saltar' });
$('btnRecargar').onclick = () => enviar({ t: 'recargar' });
$('btnNavegador').onclick = () => {
  const url = PORTAL_URL[portalActual];
  if (!url) { alert('Este certificado no tiene portal para abrir.'); return; }
  window.open(url, '_blank', 'noopener');
  const nombre = window._portalNombreActual || 'Certificado';
  if (abiertosEnNavegador.indexOf(nombre) < 0) abiertosEnNavegador.push(nombre);
  // Se salta en la app: lo resuelves en tu navegador y lo adjuntas al final.
  enviar({ t: 'saltar' });
};
$('btnCancelar').onclick = () => {
  if (confirm('Cancelar la consulta en curso?')) enviar({ t: 'cancelar' });
};

/* ---------------------------------------------------------- resultado -- */
function pintarResumen(resumen) {
  const ul = $('resumen');
  ul.innerHTML = '';
  (resumen || []).forEach(r => {
    const li = document.createElement('li');
    li.innerHTML =
      '<span class="punto ' + (r.ok ? 'ok' : 'no') + '"></span>' +
      '<span><b>' + r.portal + '</b><small>' + (r.detalle || '') + '</small></span>';
    ul.appendChild(li);
  });
}
function actualizarDescarga(m) {
  const a = $('btnDescargar');
  a.href = API + m.url + '?t=' + Date.now();     // evita cache tras adjuntar
  a.setAttribute('download', m.archivo || 'antecedentes.pdf');
}
function mostrarFin(m) {
  pintarResumen(m.resumen);
  actualizarDescarga(m);
  $('notaRedam').hidden = !redamSeleccionado;
  $('etiquetaAdjunto').value = redamSeleccionado ? 'REDAM' : '';
  $('estadoAdjunto').textContent = '';
  pantalla('pantallaFin');
}

/* ------------------------------------------------------- adjuntar PDF -- */
$('btnAdjuntar').onclick = () => $('archivoAdjunto').click();
$('archivoAdjunto').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  if (f.type && f.type !== 'application/pdf') {
    $('estadoAdjunto').textContent = 'El archivo debe ser un PDF.';
    return;
  }
  const fd = new FormData();
  fd.append('archivo', f);
  fd.append('etiqueta', $('etiquetaAdjunto').value.trim() || 'Certificado adjuntado');
  $('estadoAdjunto').textContent = 'Adjuntando...';
  try {
    const r = await fetch(API + '/api/sesion/' + sid + '/adjuntar', { method: 'POST', body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || 'No se pudo adjuntar');
    pintarResumen(j.resumen);
    actualizarDescarga(j);
    $('estadoAdjunto').textContent = 'Agregado. Vuelve a tocar "Descargar PDF consolidado".';
    $('archivoAdjunto').value = '';
  } catch (e) {
    $('estadoAdjunto').textContent = 'Error: ' + e.message;
  }
});

$('btnNueva').onclick = () => {
  if (ws) ws.close();
  ws = null; sid = null;
  pantalla('pantallaForm');
  chip('Listo', '');
};

/* --------------------------------------------------------------- PWA --- */
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

aplicarZoom();
cargarPortales();
