"""Pruebas del análisis de sentimiento y del motor en vivo (entradas/salidas).

Todas las pruebas inyectan fuentes falsas: no dependen de la red.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from oro.config import cargar_configuracion
from oro.datos import ProveedorSintetico
from oro.dominio import Direccion, EstadoOperacion, Signal, TakeProfit
from oro.notificaciones.base import Evento, Notificador
from oro.sentimiento import AnalizadorSentimiento
from oro.sentimiento.fuentes import EventoMacro, Titular
from oro.sentimiento.lexico import es_evento_alto_impacto, puntuar_texto
from oro.vivo import GestorOperaciones, RunnerVivo


# ---------- léxico ----------
def test_lexico_alcista_y_bajista():
    pos, n1 = puntuar_texto("Gold surges as safe haven demand and inflation rise")
    neg, n2 = puntuar_texto("Gold falls as strong dollar and rate hike bets grow")
    assert pos > 0 and n1 >= 2
    assert neg < 0 and n2 >= 2


def test_lexico_neutro_sin_coincidencias():
    val, n = puntuar_texto("Company announces quarterly board meeting schedule")
    assert n == 0 and val == 0.0


def test_evento_alto_impacto():
    assert es_evento_alto_impacto("US Core CPI m/m")
    assert es_evento_alto_impacto("FOMC Statement")
    assert not es_evento_alto_impacto("Retail sales minor update")


# ---------- analizador ----------
def _ahora():
    return datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)


def test_sentimiento_agrega_ponderando():
    ahora = _ahora()
    titulares = [
        Titular("Gold surges on safe haven demand", ahora, "t"),
        Titular("Inflation fears lift gold to record high", ahora, "t"),
        Titular("Weak dollar and rate cut bets boost gold", ahora, "t"),
    ]
    an = AnalizadorSentimiento(min_titulares_senal=3,
                               fuente_titulares=lambda: titulares, fuente_eventos=lambda: [])
    ctx = an.analizar(ahora)
    assert ctx.sentimiento is not None and ctx.sentimiento > 0.3
    assert ctx.n_con_senal == 3
    assert not ctx.riesgo_noticia_alta


def test_sentimiento_none_si_pocas_senales():
    an = AnalizadorSentimiento(min_titulares_senal=3,
                               fuente_titulares=lambda: [Titular("Gold rises", _ahora(), "t")],
                               fuente_eventos=lambda: [])
    ctx = an.analizar(_ahora())
    assert ctx.sentimiento is None


def test_riesgo_noticia_detecta_evento_inminente():
    ahora = _ahora()
    evento = EventoMacro("US CPI m/m", "USD", "high", ahora + timedelta(minutes=30))
    an = AnalizadorSentimiento(ventana_evento_min=60,
                               fuente_titulares=lambda: [], fuente_eventos=lambda: [evento])
    ctx = an.analizar(ahora)
    assert ctx.riesgo_noticia_alta
    assert ctx.minutos_al_evento == 30


def test_riesgo_noticia_ignora_evento_lejano():
    ahora = _ahora()
    evento = EventoMacro("US CPI m/m", "USD", "high", ahora + timedelta(hours=10))
    an = AnalizadorSentimiento(ventana_evento_min=60,
                               fuente_titulares=lambda: [], fuente_eventos=lambda: [evento])
    assert not an.analizar(ahora).riesgo_noticia_alta


# ---------- gestor de operaciones (salidas) ----------
def _signal():
    return Signal(
        momento=_ahora(), direccion=Direccion.COMPRA, entrada=2000, stop_loss=1990,
        take_profits=[TakeProfit(2010, 0.5, 1.0), TakeProfit(2020, 0.3, 2.0), TakeProfit(2030, 0.2, 3.0)],
        probabilidad=0.6, confianza=0.7, riesgo_recompensa=1.7, tamano_posicion=5.0,
    )


def test_gestor_stop_directo_es_menos_1r():
    g = GestorOperaciones(_signal())
    evs = g.actualizar(1989, _ahora())
    assert g.estado is EstadoOperacion.CERRADA_SL
    assert g.r_acumulado == pytest.approx(-1.0)
    assert evs[-1].cierra_operacion


def test_gestor_tp1_mueve_a_breakeven_y_protege():
    g = GestorOperaciones(_signal())
    tipos = [e.tipo for e in g.actualizar(2010, _ahora())]
    assert Evento.TP_ALCANZADO in tipos and Evento.MOVER_STOP in tipos
    assert g.stop_actual == 2000  # break-even.
    # Si vuelve a la entrada, cierra protegido con el parcial ya asegurado.
    g.actualizar(2000, _ahora())
    assert g.estado is EstadoOperacion.CERRADA_MANUAL
    assert g.r_acumulado == pytest.approx(0.5)


def test_gestor_todos_los_objetivos():
    g = GestorOperaciones(_signal())
    g.actualizar(2010, _ahora())
    g.actualizar(2020, _ahora())
    g.actualizar(2030, _ahora())
    assert g.estado is EstadoOperacion.CERRADA_TP
    assert g.r_acumulado == pytest.approx(1.7)


# ---------- runner en vivo ----------
class _Espia(Notificador):
    def __init__(self):
        self.eventos = []

    def enviar(self, titulo, cuerpo, evento=Evento.NUEVA_SENAL):
        self.eventos.append(evento)
        return True


def _runner_offline(**kw):
    an = AnalizadorSentimiento(min_titulares_senal=1,
                               fuente_titulares=lambda: [Titular("Gold rises on inflation", _ahora(), "t")],
                               fuente_eventos=lambda: [])
    return RunnerVivo(cargar_configuracion(),
                      proveedor=ProveedorSintetico(velas=6000, semilla=3),
                      analizador=an, **kw)


def test_runner_ciclo_offline_no_rompe():
    r = _runner_offline().ciclo()
    assert r.precio > 0
    assert "Sentimiento" in r.resumen_sentimiento
    assert r.senales_hoy >= 0


def test_runner_respeta_tope_diario():
    runner = _runner_offline()
    runner.cfg.riesgo.operaciones_max_dia = 0  # no debe abrir ninguna.
    r = runner.ciclo()
    assert r.nueva_senal is None
    assert "diario" in r.motivo_sin_entrada.lower()
