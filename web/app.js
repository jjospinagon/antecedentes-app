/* PWA - Certificados de antecedentes ------------------------------------
   El servidor corre un navegador real; aqui solo se ve su pantalla y se le
   reenvian los toques y el teclado. El captcha lo resuelve el usuario.
------------------------------------------------------------------------ */
'use strict';

const API = location.origin;               // mismo origen que sirve la PWA
const $ = (id) => document.getElementById(id);

let ws = null, sid = null, vw = 430, vh = 860, ultimoTexto = '';

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
  datos.forEach(p => {
    const l = document.createElement('label');
    l.className = 'portal';
    l.dataset.nit = p.admite_nit ? '1' : '0';
    l.innerHTML =
      '<input type="checkbox" value="' + p.id + '" checked>' +
      '<span><b>' + p.nombre + '</b><small>' + p.entidad + '</small></span>';
    cont.appendChild(l);
  });
  aplicarFiltroNit();
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
}

/* --------------------------------------------------------- arranque ---- */
$('tipoDoc').addEventListener('change', aplicarFiltroNit);

$('formulario').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const seleccion = [...document.querySelectorAll('#listaPortales input:checked')]
    .map(i => i.value);
  if (!seleccion.length) { alert('Selecciona al menos un certificado.'); return; }

  $('btnIniciar').disabled = true;
  chip('Conectando...', 'esp');

  const cuerpo = {
    tipo_doc: $('tipoDoc').value,
    numero: $('numero').value.trim(),
    fecha_expedicion: $('fecha').value || null,
    nombre: $('nombre').value.trim() || null,
    portales: seleccion
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
    pantalla('pantallaVisor');
    abrirSocket();
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
  ws.onclose = () => chip('Desconectado', 'err');
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
        $('portalNombre').textContent = m.nombre || '';
        $('portalEntidad').textContent = m.entidad || '';
        $('contador').textContent = (m.idx || 0) + '/' + (m.total || 0);
        const ins = $('instruccion');
        ins.textContent = m.msg || '';
        const interactivo = (m.fase === 'captcha' || m.fase === 'revision');
        ins.classList.toggle('accion', m.fase === 'revision');
        ['btnContinuar', 'entrada', 'btnEnter', 'btnBorrar', 'btnRecargar', 'btnSaltar']
          .forEach(id => { $(id).disabled = !interactivo; });
        $('btnContinuar').textContent =
          m.fase === 'revision' ? 'Guardar y continuar' : 'Continuar';
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

/* -------------------------------------------- toques sobre la pantalla -- */
$('pantalla').addEventListener('click', (ev) => {
  const img = ev.currentTarget;
  const r = img.getBoundingClientRect();
  if (!r.width) return;
  const x = ((ev.clientX - r.left) / r.width) * vw;
  const y = ((ev.clientY - r.top) / r.height) * vh;
  enviar({ t: 'click', x: Math.round(x), y: Math.round(y) });
  $('entrada').value = '';
  ultimoTexto = '';
  $('entrada').focus();
});

$('marco').addEventListener('wheel', (ev) => {
  ev.preventDefault();
  enviar({ t: 'scroll', dy: ev.deltaY });
}, { passive: false });

/* ------------------------------------------------------ teclado local -- */
$('entrada').addEventListener('input', (ev) => {
  const v = ev.target.value;
  if (v.startsWith(ultimoTexto)) {
    const nuevo = v.slice(ultimoTexto.length);
    if (nuevo) enviar({ t: 'texto', v: nuevo });
  } else {
    const borrar = ultimoTexto.length - v.length;
    for (let i = 0; i < Math.max(borrar, 0); i++) enviar({ t: 'tecla', k: 'Backspace' });
  }
  ultimoTexto = v;
});
$('entrada').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter') { ev.preventDefault(); enviar({ t: 'tecla', k: 'Enter' }); }
});
$('btnEnter').onclick = () => enviar({ t: 'tecla', k: 'Enter' });
$('btnBorrar').onclick = () => {
  enviar({ t: 'tecla', k: 'Backspace' });
  ultimoTexto = ultimoTexto.slice(0, -1);
  $('entrada').value = ultimoTexto;
};

/* ---------------------------------------------------------- acciones --- */
$('btnContinuar').onclick = () => {
  $('btnContinuar').disabled = true;
  $('cargando').classList.remove('oculto');
  $('entrada').value = ''; ultimoTexto = '';
  enviar({ t: 'continuar' });
};
$('btnSaltar').onclick = () => enviar({ t: 'saltar' });
$('btnRecargar').onclick = () => enviar({ t: 'recargar' });
$('btnCancelar').onclick = () => {
  if (confirm('Cancelar la consulta en curso?')) enviar({ t: 'cancelar' });
};

/* ---------------------------------------------------------- resultado -- */
function mostrarFin(m) {
  const ul = $('resumen');
  ul.innerHTML = '';
  (m.resumen || []).forEach(r => {
    const li = document.createElement('li');
    li.innerHTML =
      '<span class="punto ' + (r.ok ? 'ok' : 'no') + '"></span>' +
      '<span><b>' + r.portal + '</b><small>' + (r.detalle || '') + '</small></span>';
    ul.appendChild(li);
  });
  const a = $('btnDescargar');
  a.href = API + m.url;
  a.setAttribute('download', m.archivo || 'antecedentes.pdf');
  pantalla('pantallaFin');
}

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

cargarPortales();
