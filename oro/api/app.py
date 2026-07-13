"""API FastAPI + panel de control mínimo.

Endpoints:
    GET  /oro/salud            estado del servicio.
    GET  /oro/senal            análisis del estado de mercado actual.
    POST /oro/backtest         ejecuta un backtest y devuelve las métricas.
    GET  /oro/panel            panel de control HTML (dashboard).

El panel es autocontenido (sin dependencias externas de red) para poder abrirse
desde el móvil. En producción, la señal y las métricas se refrescarían contra
datos reales.
"""

from __future__ import annotations

from typing import Optional

from ..config import cargar_configuracion
from ..servicio import ServicioOro


def _serializar_resultado(resultado) -> dict:
    datos = {
        "hay_operacion": resultado.hay_operacion,
        "mensaje": resultado.mensaje,
        "puntuacion": round(resultado.puntuacion, 4),
        "motivos_no": resultado.motivos_no,
    }
    if resultado.signal is not None:
        s = resultado.signal
        datos["signal"] = {
            "direccion": s.direccion.value,
            "entrada": round(s.entrada, 2),
            "stop_loss": round(s.stop_loss, 2),
            "take_profits": [
                {"precio": round(tp.precio, 2), "fraccion": tp.fraccion, "r": tp.r_multiple}
                for tp in s.take_profits
            ],
            "probabilidad": round(s.probabilidad, 4),
            "confianza": round(s.confianza, 4),
            "riesgo_recompensa": round(s.riesgo_recompensa, 2),
            "tamano_posicion": round(s.tamano_posicion, 2),
            "contexto_tecnico": s.contexto_tecnico,
            "motivos_entrada": s.motivos_entrada,
            "riesgos": s.riesgos,
        }
    return datos


def crear_app(servicio: Optional[ServicioOro] = None):
    """Crea la aplicación FastAPI. Se inyecta el servicio para poder testear."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    servicio = servicio or ServicioOro()
    app = FastAPI(
        title="Sistema XAU/USD (ORO)",
        description="Análisis de oro y generación de señales A+. "
                    "Herramienta de apoyo, no asesoramiento financiero.",
        version="0.1.0",
    )

    @app.get("/oro/salud")
    def salud() -> dict:
        problemas = servicio.cfg.validar()
        return {
            "estado": "ok" if not problemas else "config_invalida",
            "simbolo": servicio.cfg.simbolo,
            "modelo_cargado": servicio.motor.modelo is not None,
            "problemas_config": problemas,
        }

    @app.get("/oro/senal")
    def senal(velas: int = 500) -> dict:
        return _serializar_resultado(servicio.analizar_ahora(velas))

    @app.post("/oro/backtest")
    def backtest(velas: int = 6000) -> dict:
        res = servicio.backtest(velas)
        m = res.metricas
        return {
            "operaciones": m.operaciones,
            "win_rate": round(m.win_rate, 4),
            "profit_factor": round(m.profit_factor, 3) if m.profit_factor != float("inf") else None,
            "expectancy_r": round(m.expectancy_r, 4),
            "sharpe": round(m.sharpe, 3),
            "max_drawdown": round(m.max_drawdown, 4),
            "rentabilidad_total": round(m.rentabilidad_total, 4),
            "cagr": round(m.cagr, 4),
            "racha_perdedora_max": m.racha_perdedora_max,
            "nota": "Métricas sobre los datos configurados. Validar en real/demo.",
        }

    @app.get("/oro/panel", response_class=HTMLResponse)
    def panel() -> str:
        return _PANEL_HTML

    return app


_PANEL_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panel XAU/USD</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: system-ui, sans-serif; background:#0b0e14; color:#e6e6e6; margin:0; padding:1rem; }
  h1 { font-size:1.2rem; color:#e8b923; }
  .tarjeta { background:#141a24; border:1px solid #232c3a; border-radius:12px; padding:1rem; margin:.6rem 0; }
  .fila { display:flex; justify-content:space-between; padding:.2rem 0; border-bottom:1px solid #1c2430; }
  button { background:#e8b923; color:#111; border:0; border-radius:8px; padding:.6rem 1rem; font-weight:600; }
  .compra { color:#3ddc84; } .venta { color:#ff6b6b; } .muted { color:#8a93a3; font-size:.85rem; }
  pre { white-space:pre-wrap; }
</style></head>
<body>
  <h1>◆ Panel XAU/USD — Señales A+</h1>
  <p class="muted">Herramienta de análisis. No es asesoramiento financiero. El trading conlleva riesgo de pérdida.</p>
  <div class="tarjeta"><button onclick="cargar()">Analizar mercado</button>
    <button onclick="backtest()">Backtest</button></div>
  <div class="tarjeta" id="senal">Pulse «Analizar mercado».</div>
  <div class="tarjeta" id="metricas"><span class="muted">Métricas del backtest aquí.</span></div>
<script>
async function cargar(){
  const d = await (await fetch('/oro/senal')).json();
  const c = document.getElementById('senal');
  if(!d.hay_operacion){ c.innerHTML = '<b>'+d.mensaje+'</b><br><span class=muted>'+(d.motivos_no||[]).join('<br>')+'</span>'; return; }
  const s = d.signal; const cls = s.direccion==='compra'?'compra':'venta';
  let tp = s.take_profits.map((t,i)=>'TP'+(i+1)+': '+t.precio+' ('+t.r+'R)').join('<br>');
  c.innerHTML = '<h3 class="'+cls+'">'+s.direccion.toUpperCase()+' @ '+s.entrada+'</h3>'+
    '<div class=fila><span>Stop</span><span>'+s.stop_loss+'</span></div>'+
    '<div class=fila><span>Objetivos</span><span>'+tp+'</span></div>'+
    '<div class=fila><span>Probabilidad</span><span>'+Math.round(s.probabilidad*100)+'%</span></div>'+
    '<div class=fila><span>Confianza</span><span>'+Math.round(s.confianza*100)+'%</span></div>'+
    '<div class=fila><span>R:R</span><span>'+s.riesgo_recompensa+'</span></div>'+
    '<p class=muted>'+s.contexto_tecnico+'</p>';
}
async function backtest(){
  const m = document.getElementById('metricas'); m.innerHTML='Ejecutando backtest…';
  const d = await (await fetch('/oro/backtest',{method:'POST'})).json();
  m.innerHTML = '<div class=fila><span>Operaciones</span><span>'+d.operaciones+'</span></div>'+
    '<div class=fila><span>Win rate</span><span>'+Math.round(d.win_rate*100)+'%</span></div>'+
    '<div class=fila><span>Profit Factor</span><span>'+d.profit_factor+'</span></div>'+
    '<div class=fila><span>Expectancy</span><span>'+d.expectancy_r+'R</span></div>'+
    '<div class=fila><span>Max Drawdown</span><span>'+Math.round(d.max_drawdown*100)+'%</span></div>'+
    '<p class=muted>'+d.nota+'</p>';
}
</script>
</body></html>"""
