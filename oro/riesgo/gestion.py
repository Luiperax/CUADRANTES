"""Cálculo de niveles, dimensionado de posición y guardas de no-operar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..config import ConfiguracionSistema
from ..dominio import Direccion, MarketSnapshot, TakeProfit


@dataclass(frozen=True, slots=True)
class NivelesOperacion:
    entrada: float
    stop_loss: float
    take_profits: List[TakeProfit]
    riesgo_por_unidad: float
    riesgo_recompensa: float  # R:R medio ponderado por el reparto de la posición.


def calcular_niveles(
    entrada: float,
    direccion: Direccion,
    atr: float,
    cfg: ConfiguracionSistema,
) -> NivelesOperacion:
    """Calcula stop y objetivos a partir del ATR (stop dinámico por volatilidad).

    El stop se sitúa a ``atr_stop_mult × ATR`` de la entrada, y los objetivos en
    múltiplos de ese riesgo (R). Así el sistema se adapta a la volatilidad: en
    mercados agitados, stops más amplios; en mercados tranquilos, más ceñidos.
    """
    r = cfg.riesgo
    distancia = max(atr * r.atr_stop_mult, 1e-9)
    signo = direccion.signo
    stop = entrada - signo * distancia

    take_profits: List[TakeProfit] = []
    for fraccion, r_obj in zip(r.reparto_tp, r.r_objetivos):
        precio_tp = entrada + signo * distancia * r_obj
        take_profits.append(TakeProfit(precio=precio_tp, fraccion=fraccion, r_multiple=r_obj))

    rr_ponderado = sum(tp.fraccion * tp.r_multiple for tp in take_profits)
    return NivelesOperacion(
        entrada=entrada,
        stop_loss=stop,
        take_profits=take_profits,
        riesgo_por_unidad=distancia,
        riesgo_recompensa=rr_ponderado,
    )


def dimensionar_posicion(
    riesgo_por_unidad: float,
    cfg: ConfiguracionSistema,
    riesgo_pct: float | None = None,
) -> float:
    """Tamaño de posición (en onzas) para arriesgar exactamente el % configurado.

    tamaño = (capital × riesgo%) / distancia_al_stop

    De este modo, la pérdida máxima si salta el stop es siempre el porcentaje
    fijado del capital, independientemente de la volatilidad o del precio.
    """
    pct = riesgo_pct if riesgo_pct is not None else cfg.riesgo.riesgo_por_operacion
    if riesgo_por_unidad <= 0:
        return 0.0
    riesgo_moneda = cfg.capital * pct
    return riesgo_moneda / riesgo_por_unidad


def evaluar_guardas(snapshot: MarketSnapshot, cfg: ConfiguracionSistema) -> List[str]:
    """Devuelve la lista de motivos por los que NO se debe operar ahora.

    Si la lista está vacía, las condiciones de mercado permiten (no obligan) a
    operar. Estas guardas son incondicionales: da igual lo buena que parezca la
    señal, si alguna guarda salta, no se opera.
    """
    motivos: List[str] = []
    c = cfg.calidad

    if snapshot.spread > c.spread_max:
        motivos.append(
            f"Spread demasiado alto ({snapshot.spread:.2f} > {c.spread_max:.2f})."
        )
    if snapshot.atr > c.atr_max:
        motivos.append(
            f"Volatilidad extrema (ATR {snapshot.atr:.2f} > {c.atr_max:.2f})."
        )
    if snapshot.atr < c.atr_min:
        motivos.append(
            f"Mercado demasiado plano (ATR {snapshot.atr:.2f} < {c.atr_min:.2f})."
        )
    if snapshot.riesgo_noticia_alta:
        motivos.append("Noticia macro de alto impacto próxima: riesgo de spike.")
    return motivos
