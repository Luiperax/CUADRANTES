"""Servicio web en vivo: panel móvil + motor ejecutándose en segundo plano.

A diferencia de :mod:`oro.api.app` (endpoints bajo demanda), aquí el motor
:class:`~oro.vivo.RunnerVivo` corre en un **hilo de fondo** que revisa el
mercado cada ``intervalo`` segundos, envía las notificaciones (Telegram, etc.) y
mantiene el estado en vivo que sirve el panel. Pensado para desplegarse en la
nube y abrirlo desde el móvil con una URL fija.

Protección opcional por clave: si se define ``ORO_PANEL_CLAVE`` (o se pasa
``clave``), el panel y el estado exigen ``?clave=...`` — recomendable si la URL
es pública.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from ..vivo import RunnerVivo


def crear_app_vivo(
    runner: Optional[RunnerVivo] = None,
    intervalo: int = 900,
    clave: Optional[str] = None,
    arrancar_scheduler: bool = True,
):
    """Crea la app FastAPI en vivo. El ``runner`` se inyecta para poder testear."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse

    runner = runner or RunnerVivo()
    clave = clave if clave is not None else os.getenv("ORO_PANEL_CLAVE", "")
    estado_hilo = {"stop": threading.Event(), "hilo": None, "ultimo_error": None}

    def _bucle() -> None:
        stop = estado_hilo["stop"]
        # Primer ciclo inmediato para tener estado desde el arranque.
        while not stop.is_set():
            try:
                runner.ciclo()
                estado_hilo["ultimo_error"] = None
            except Exception as e:  # noqa: BLE001 — el hilo no debe morir.
                estado_hilo["ultimo_error"] = f"{type(e).__name__}: {e}"[:200]
            stop.wait(intervalo)

    @asynccontextmanager
    async def _ciclo_vida(_app):
        # Arranque: lanza el motor en segundo plano.
        if arrancar_scheduler and estado_hilo["hilo"] is None:
            hilo = threading.Thread(target=_bucle, name="oro-vivo", daemon=True)
            estado_hilo["hilo"] = hilo
            hilo.start()
        try:
            yield
        finally:
            estado_hilo["stop"].set()  # Cierre: detiene el bucle.

    app = FastAPI(
        title="XAU/USD en vivo (ORO)",
        description="Panel móvil y motor de señales en vivo. "
                    "Herramienta de análisis, no asesoramiento financiero.",
        version="0.1.0",
        lifespan=_ciclo_vida,
    )

    def _verificar(clave_req: Optional[str]) -> None:
        if clave and clave_req != clave:
            raise HTTPException(status_code=401, detail="Clave incorrecta.")

    @app.get("/oro/salud")
    def salud() -> dict:
        return {
            "estado": "ok",
            "scheduler_activo": estado_hilo["hilo"] is not None,
            "ultimo_error": estado_hilo["ultimo_error"],
            "protegido": bool(clave),
        }

    @app.get("/oro/estado")
    def estado(clave: Optional[str] = Query(default=None)) -> dict:
        _verificar(clave)
        return runner.estado()

    @app.post("/oro/ciclo")
    def ciclo_manual(clave: Optional[str] = Query(default=None)) -> dict:
        """Fuerza un ciclo ahora (útil para probar sin esperar al intervalo)."""
        _verificar(clave)
        runner.ciclo()
        return runner.estado()

    @app.get("/", response_class=HTMLResponse)
    @app.get("/oro/panel", response_class=HTMLResponse)
    def panel() -> str:
        return _PANEL_VIVO_HTML

    return app


_PANEL_VIVO_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>XAU/USD en vivo</title>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{font-family:system-ui,-apple-system,sans-serif;background:#0b0e14;color:#e6e6e6;margin:0;padding:14px;max-width:680px;margin:0 auto}
  h1{font-size:1.15rem;color:#e8b923;margin:.2rem 0}
  .muted{color:#8a93a3;font-size:.82rem}
  .tarjeta{background:#141a24;border:1px solid #232c3a;border-radius:14px;padding:14px;margin:10px 0}
  .precio{font-size:2rem;font-weight:700}
  .fila{display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid #1c2430}
  .fila:last-child{border-bottom:0}
  .compra{color:#3ddc84}.venta{color:#ff6b6b}
  .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.72rem;font-weight:600}
  .be{background:#1c3a2a;color:#3ddc84}
  .aviso{background:#2a1a1a;border-color:#4a2a2a}
  .ev{font-size:.82rem;padding:6px 0;border-bottom:1px solid #1c2430}
  input,button{font:inherit;border-radius:8px;border:1px solid #2a3446;background:#0f141d;color:#e6e6e6;padding:8px}
  button{background:#e8b923;color:#111;font-weight:700;border:0}
</style></head>
<body>
  <h1>◆ XAU/USD — en vivo</h1>
  <p class="muted">Herramienta de análisis, no asesoramiento financiero. El trading conlleva riesgo de pérdida. La probabilidad es una estimación, no una garantía.</p>
  <div id="login" class="tarjeta" style="display:none">
    <div class="muted">Panel protegido. Introduce la clave:</div>
    <div style="display:flex;gap:8px;margin-top:8px"><input id="clave" type="password" placeholder="clave" style="flex:1"><button onclick="guardarClave()">Entrar</button></div>
  </div>
  <div class="tarjeta">
    <div class="muted" id="ts">Cargando…</div>
    <div class="precio" id="precio">—</div>
    <div class="muted" id="sent">—</div>
    <div class="muted" id="conteo" style="margin-top:6px">—</div>
  </div>
  <h2 style="font-size:.95rem;color:#e8b923">Operaciones abiertas</h2>
  <div id="abiertas"><div class="tarjeta muted">Sin operaciones abiertas.</div></div>
  <h2 style="font-size:.95rem;color:#e8b923">Últimos eventos</h2>
  <div id="historial" class="tarjeta"><span class="muted">—</span></div>
<script>
function clave(){return localStorage.getItem('oro_clave')||''}
function guardarClave(){localStorage.setItem('oro_clave',document.getElementById('clave').value);document.getElementById('login').style.display='none';cargar()}
async function cargar(){
  try{
    const q = clave()?('?clave='+encodeURIComponent(clave())):'';
    const res = await fetch('/oro/estado'+q);
    if(res.status===401){document.getElementById('login').style.display='block';return}
    const d = await res.json();
    document.getElementById('ts').textContent = d.actualizado? ('Actualizado: '+d.actualizado.replace('T',' ').slice(0,16)) : 'Esperando primer ciclo…';
    document.getElementById('precio').textContent = d.precio? ('$'+d.precio) : '—';
    document.getElementById('sent').textContent = d.sentimiento||'';
    document.getElementById('conteo').textContent = 'Señales hoy: '+d.senales_hoy+' / '+d.tope_diario+(d.motivo_sin_entrada?('  ·  '+d.motivo_sin_entrada):'');
    // abiertas
    const cont = document.getElementById('abiertas');
    if(!d.abiertas || !d.abiertas.length){cont.innerHTML='<div class="tarjeta muted">Sin operaciones abiertas.</div>'}
    else{cont.innerHTML = d.abiertas.map(function(o){
      const cls = o.direccion==='compra'?'compra':'venta';
      const be = o.en_breakeven?'<span class="pill be">SIN RIESGO (BE)</span>':'';
      const tps = o.objetivos.map(function(t,i){return 'TP'+(i+1)+': '+t.precio+(t.alcanzado?' ✓':'')}).join(' · ');
      const flot = (o.r_flotante!=null)?(' · flotante '+o.r_flotante+'R'):'';
      return '<div class="tarjeta"><div class="fila"><b class="'+cls+'">'+o.direccion.toUpperCase()+' @ '+o.entrada+'</b>'+be+'</div>'+
             '<div class="fila"><span>Stop actual</span><span>'+o.stop_actual+'</span></div>'+
             '<div class="fila"><span>Objetivos</span><span style="text-align:right">'+tps+'</span></div>'+
             '<div class="fila"><span>Asegurado</span><span>'+o.r_asegurado+'R'+flot+'</span></div></div>';
    }).join('')}
    // historial
    const h = document.getElementById('historial');
    if(!d.historial||!d.historial.length){h.innerHTML='<span class="muted">Sin eventos todavía.</span>'}
    else{h.innerHTML = d.historial.slice(0,12).map(function(e){
      const t=(e.momento||'').replace('T',' ').slice(5,16);
      return '<div class="ev"><span class="muted">'+t+'</span> · <b>'+(e.tipo||'').toUpperCase()+'</b> · '+(e.mensaje||'')+'</div>';
    }).join('')}
  }catch(err){document.getElementById('ts').textContent='Error de conexión, reintentando…'}
}
cargar(); setInterval(cargar, 30000);
</script>
</body></html>"""
