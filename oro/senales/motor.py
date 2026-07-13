"""Motor de confluencia y filtro A+.

El motor NO intenta adivinar el mercado. Mide *ventaja*: cuánta confluencia de
factores independientes apunta en la misma dirección, la traduce en una
probabilidad estimada y solo deja pasar las oportunidades que superan umbrales
estrictos de probabilidad, confianza y relación beneficio/riesgo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from ..config import ConfiguracionSistema
from ..dominio import Direccion, MarketSnapshot, Signal
from ..estructura import analizar_estructura
from ..estructura.analisis import Tendencia
from ..features import construir_features
from ..indicadores import calcular_todos
from ..riesgo import calcular_niveles, dimensionar_posicion, evaluar_guardas

_FRASE_SIN_OPERACION = "Hoy no existen operaciones con suficiente ventaja estadística."


@dataclass(slots=True)
class ResultadoAnalisis:
    """Resultado de analizar el mercado en un instante.

    Si ``signal`` es ``None``, no hay operación A+ y ``mensaje`` explica por qué.
    """

    hay_operacion: bool
    mensaje: str
    signal: Optional[Signal] = None
    puntuacion: float = 0.0
    direccion_sesgo: Optional[Direccion] = None
    motivos_no: List[str] = field(default_factory=list)


class MotorSenales:
    def __init__(self, cfg: ConfiguracionSistema, modelo=None) -> None:
        self.cfg = cfg
        self.modelo = modelo  # objeto con .predecir_proba(features_row) opcional.

    # ---- sesgo direccional (lo aporta la estructura, no los indicadores) ----
    def _sesgo(self, estructura, ind_ultima) -> Optional[Direccion]:
        # CHoCH tiene prioridad (posible giro); luego BOS; luego tendencia.
        if estructura.ultimo_choch == "alcista":
            return Direccion.COMPRA
        if estructura.ultimo_choch == "bajista":
            return Direccion.VENTA
        if estructura.ultimo_bos == "alcista" or estructura.tendencia is Tendencia.ALCISTA:
            return Direccion.COMPRA
        if estructura.ultimo_bos == "bajista" or estructura.tendencia is Tendencia.BAJISTA:
            return Direccion.VENTA
        return None

    # ---- puntuación de confluencia (0..1) con factores independientes ----
    def _puntuar(self, direccion, estructura, ind, snapshot) -> tuple[float, List[str]]:
        signo = direccion.signo
        factores: List[tuple[str, float, str]] = []  # (nombre, peso, motivo)

        # 1) Alineación con la tendencia estructural.
        alineado = (
            (direccion is Direccion.COMPRA and estructura.tendencia is Tendencia.ALCISTA)
            or (direccion is Direccion.VENTA and estructura.tendencia is Tendencia.BAJISTA)
        )
        factores.append(("tendencia", 1.0 if alineado else 0.0,
                         "A favor de la tendencia estructural." if alineado
                         else "Contra o sin tendencia clara."))

        # 2) Fuerza de tendencia (ADX). Penaliza mercado lateral.
        adx = float(ind["adx"]) if pd.notna(ind["adx"]) else 0.0
        fuerza = max(0.0, min(1.0, (adx - self.cfg.calidad.adx_lateral) / 15.0))
        factores.append(("adx", fuerza, f"ADX {adx:.0f} (fuerza de tendencia)."))

        # 3) Momentum de la dirección (MACD histograma y DI).
        macd_h = float(ind["macd_hist"]) if pd.notna(ind["macd_hist"]) else 0.0
        di_ok = signo * (float(ind["plus_di"]) - float(ind["minus_di"])) > 0
        mom = 0.0
        if signo * macd_h > 0:
            mom += 0.5
        if di_ok:
            mom += 0.5
        factores.append(("momentum", mom, "Momentum (MACD/DI) a favor." if mom >= 0.5
                         else "Momentum débil o en contra."))

        # 4) RSI no en extremo contrario (evita comprar sobrecomprado, etc.).
        rsi = float(ind["rsi_14"]) if pd.notna(ind["rsi_14"]) else 50.0
        if direccion is Direccion.COMPRA:
            rsi_ok = 1.0 if 45 <= rsi <= 68 else (0.5 if rsi < 45 else 0.0)
        else:
            rsi_ok = 1.0 if 32 <= rsi <= 55 else (0.5 if rsi > 55 else 0.0)
        factores.append(("rsi", rsi_ok, f"RSI {rsi:.0f} en zona favorable."
                         if rsi_ok >= 0.5 else f"RSI {rsi:.0f} en extremo contrario."))

        # 5) Localización: cerca de un order block/FVG a favor (entrada con ventaja).
        loc = 0.0
        precio = snapshot.precio
        for ob in estructura.order_blocks:
            if ob.alcista == (direccion is Direccion.COMPRA):
                if ob.inferior <= precio <= ob.superior * 1.002:
                    loc = 1.0
        for fvg in estructura.fvgs:
            if fvg.alcista == (direccion is Direccion.COMPRA):
                if fvg.inferior <= precio <= fvg.superior:
                    loc = max(loc, 0.7)
        factores.append(("localizacion", loc, "Precio en zona institucional (OB/FVG)."
                         if loc > 0 else "Sin zona de valor cercana."))

        # 6) Barrido de liquidez a favor del giro (trampa de liquidez).
        barrido = 0.0
        if estructura.barrido_liquidez == "alto" and direccion is Direccion.VENTA:
            barrido = 1.0
        elif estructura.barrido_liquidez == "bajo" and direccion is Direccion.COMPRA:
            barrido = 1.0
        factores.append(("liquidez", barrido, "Barrido de liquidez a favor."
                         if barrido > 0 else "Sin barrido relevante."))

        # 7) Lado correcto del VWAP.
        vwap = float(ind["vwap"]) if pd.notna(ind["vwap"]) else precio
        vwap_ok = 1.0 if signo * (precio - vwap) > 0 else 0.0
        factores.append(("vwap", vwap_ok, "Precio en el lado correcto del VWAP."
                         if vwap_ok else "Precio en el lado contrario del VWAP."))

        # Pesos (la estructura pesa más que los indicadores de confirmación).
        pesos = {"tendencia": 0.22, "adx": 0.12, "momentum": 0.16, "rsi": 0.10,
                 "localizacion": 0.20, "liquidez": 0.12, "vwap": 0.08}
        puntuacion = sum(pesos[n] * v for n, v, _ in factores)
        motivos = [m for n, v, m in factores if v >= 0.5]
        return puntuacion, motivos

    def analizar(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> ResultadoAnalisis:
        """Analiza el histórico + instantánea y decide si hay operación A+."""
        # Guardas incondicionales de riesgo primero.
        guardas = evaluar_guardas(snapshot, self.cfg)
        if guardas:
            return ResultadoAnalisis(False, _FRASE_SIN_OPERACION, motivos_no=guardas)

        enriquecido = calcular_todos(df)
        ind = enriquecido.iloc[-1]
        estructura = analizar_estructura(df)

        direccion = self._sesgo(estructura, ind)
        if direccion is None:
            return ResultadoAnalisis(
                False, _FRASE_SIN_OPERACION,
                motivos_no=["Sin sesgo direccional claro (mercado en rango)."],
            )

        puntuacion, motivos_entrada = self._puntuar(direccion, estructura, ind, snapshot)

        # Probabilidad: modelo ML si existe; si no, mapeo prudente de la puntuación.
        if self.modelo is not None:
            feats = construir_features(df).iloc[[-1]]
            probabilidad = float(self.modelo.predecir_proba(feats)[0])
        else:
            # Sin modelo: probabilidad conservadora derivada de la confluencia.
            probabilidad = 0.40 + 0.35 * puntuacion

        confianza = 0.5 * puntuacion + 0.5 * min(1.0, len(motivos_entrada) / 5.0)

        c = self.cfg.calidad
        motivos_no: List[str] = []
        if puntuacion < c.puntuacion_minima:
            motivos_no.append(f"Confluencia insuficiente ({puntuacion:.2f} < {c.puntuacion_minima}).")
        if probabilidad < c.prob_minima:
            motivos_no.append(f"Probabilidad estimada baja ({probabilidad:.0%} < {c.prob_minima:.0%}).")
        if confianza < c.confianza_minima:
            motivos_no.append(f"Confianza insuficiente ({confianza:.0%} < {c.confianza_minima:.0%}).")

        niveles = calcular_niveles(snapshot.precio, direccion, snapshot.atr, self.cfg)
        if niveles.riesgo_recompensa < self.cfg.riesgo.r_recompensa_min:
            motivos_no.append(
                f"R:R insuficiente ({niveles.riesgo_recompensa:.2f} < {self.cfg.riesgo.r_recompensa_min})."
            )

        if motivos_no:
            return ResultadoAnalisis(
                False, _FRASE_SIN_OPERACION, puntuacion=puntuacion,
                direccion_sesgo=direccion, motivos_no=motivos_no,
            )

        tamano = dimensionar_posicion(niveles.riesgo_por_unidad, self.cfg)
        signal = Signal(
            momento=snapshot.momento,
            direccion=direccion,
            entrada=niveles.entrada,
            stop_loss=niveles.stop_loss,
            take_profits=niveles.take_profits,
            probabilidad=min(0.95, probabilidad),
            confianza=min(1.0, confianza),
            riesgo_recompensa=niveles.riesgo_recompensa,
            tamano_posicion=tamano,
            contexto_macro=self._texto_macro(snapshot),
            contexto_tecnico=(
                f"Tendencia {estructura.tendencia.value}; "
                f"BOS={estructura.ultimo_bos}; CHoCH={estructura.ultimo_choch}; "
                f"ADX {float(ind['adx']):.0f}."
            ),
            factores_fundamentales=self._texto_fundamental(snapshot),
            motivos_entrada=motivos_entrada,
            motivos_no_entrada=["Ninguno relevante supera el umbral."],
            riesgos=self._riesgos(snapshot),
            duracion_estimada="1–3 sesiones (intradía a swing corto).",
            puntuacion=puntuacion,
        )
        return ResultadoAnalisis(
            True, signal.resumen(), signal=signal, puntuacion=puntuacion,
            direccion_sesgo=direccion,
        )

    # ---- textos de explicabilidad ----
    @staticmethod
    def _texto_macro(s: MarketSnapshot) -> str:
        partes = []
        if s.dxy is not None:
            partes.append(f"DXY {s.dxy:.2f}")
        if s.rendimiento_10y is not None:
            partes.append(f"UST10Y {s.rendimiento_10y:.2f}%")
        partes.append(f"sesión {s.sesion.value}")
        return "; ".join(partes) if partes else "Contexto macro no disponible."

    @staticmethod
    def _texto_fundamental(s: MarketSnapshot) -> str:
        if s.sentimiento is None:
            return "Sentimiento no disponible."
        etiqueta = "alcista" if s.sentimiento > 0.15 else "bajista" if s.sentimiento < -0.15 else "neutro"
        return f"Sentimiento agregado {s.sentimiento:+.2f} ({etiqueta})."

    @staticmethod
    def _riesgos(s: MarketSnapshot) -> List[str]:
        riesgos = ["El mercado puede invalidar la estructura en cualquier momento."]
        if s.riesgo_noticia_alta:
            riesgos.append("Evento macro próximo con posible spike de volatilidad.")
        return riesgos
