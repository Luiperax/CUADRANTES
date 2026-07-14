"""Gestor de una operación abierta: decide y notifica las SALIDAS.

Es la pieza que responde a «¿cuándo salgo?». Dada una señal ejecutada, sigue el
precio y va generando eventos de gestión conforme se cumplen las condiciones:

1. Se alcanza un objetivo parcial (TP): se cierra su fracción.
2. Tras el primer objetivo, el stop se mueve a *break-even* (entrada): la
   operación pasa a riesgo cero.
3. Si el precio toca el stop vigente: se cierra el resto (en pérdida, o a
   break-even si ya se movió).
4. Cuando se cierran todas las fracciones, la operación termina.

El gestor es determinista y se prueba sin red ni tiempo real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from ..dominio import Direccion, EstadoOperacion, Signal
from ..notificaciones.base import Evento


@dataclass(slots=True)
class EventoGestion:
    tipo: Evento
    momento: datetime
    precio: float
    mensaje: str
    r_acumulado: float          # resultado acumulado de la operación, en R.
    cierra_operacion: bool = False


@dataclass(slots=True)
class _NivelTP:
    precio: float
    fraccion: float
    r_multiple: float
    alcanzado: bool = False


class GestorOperaciones:
    def __init__(self, signal: Signal, entrada_real: float | None = None) -> None:
        self.signal = signal
        self.direccion = signal.direccion
        self.entrada = entrada_real if entrada_real is not None else signal.entrada
        self._riesgo = abs(self.entrada - signal.stop_loss)
        self.stop_actual = signal.stop_loss
        self._en_breakeven = False
        self.niveles = [
            _NivelTP(tp.precio, tp.fraccion, tp.r_multiple) for tp in signal.take_profits
        ]
        self.restante = 1.0
        self.r_acumulado = 0.0
        self.estado = EstadoOperacion.ABIERTA
        self.abierta_en = signal.momento

    def _r_en(self, precio: float) -> float:
        if self._riesgo <= 0:
            return 0.0
        return self.direccion.signo * (precio - self.entrada) / self._riesgo

    def actualizar(self, precio: float, momento: datetime) -> List[EventoGestion]:
        """Procesa un nuevo precio y devuelve los eventos de gestión generados."""
        if self.estado is not EstadoOperacion.ABIERTA:
            return []

        eventos: List[EventoGestion] = []
        signo = self.direccion.signo

        # 1) ¿Toca el stop vigente? (comprobación pesimista, antes que los TP).
        toca_stop = (precio <= self.stop_actual) if signo > 0 else (precio >= self.stop_actual)
        if toca_stop:
            r_cierre = self._r_en(self.stop_actual)
            self.r_acumulado += self.restante * r_cierre
            self.restante = 0.0
            if self._en_breakeven:
                self.estado = EstadoOperacion.CERRADA_MANUAL
                msg = (f"Cierre en BREAK-EVEN a {self.stop_actual:.2f}. "
                       f"Operación protegida. Resultado total: {self.r_acumulado:+.2f}R.")
                tipo = Evento.CIERRE
            else:
                self.estado = EstadoOperacion.CERRADA_SL
                msg = (f"STOP alcanzado a {self.stop_actual:.2f}. "
                       f"Salir. Resultado total: {self.r_acumulado:+.2f}R.")
                tipo = Evento.CIERRE
            eventos.append(EventoGestion(tipo, momento, self.stop_actual, msg,
                                         self.r_acumulado, cierra_operacion=True))
            return eventos

        # 2) ¿Se alcanzan objetivos? (en orden).
        for i, nivel in enumerate(self.niveles, start=1):
            if nivel.alcanzado:
                continue
            alcanzado = (precio >= nivel.precio) if signo > 0 else (precio <= nivel.precio)
            if not alcanzado:
                break
            nivel.alcanzado = True
            self.r_acumulado += nivel.fraccion * nivel.r_multiple
            self.restante -= nivel.fraccion
            eventos.append(EventoGestion(
                Evento.TP_ALCANZADO, momento, nivel.precio,
                f"TP{i} alcanzado a {nivel.precio:.2f} ({nivel.r_multiple:.1f}R). "
                f"Cerrar {nivel.fraccion:.0%} de la posición.",
                self.r_acumulado,
            ))
            # Tras el primer objetivo: proteger a break-even.
            if not self._en_breakeven:
                self._en_breakeven = True
                self.stop_actual = self.entrada
                eventos.append(EventoGestion(
                    Evento.MOVER_STOP, momento, self.entrada,
                    f"Mover STOP a break-even ({self.entrada:.2f}). "
                    f"Operación sin riesgo a partir de ahora.",
                    self.r_acumulado,
                ))

        # 3) ¿Se cerró toda la posición con los objetivos?
        if self.restante <= 1e-9 and self.estado is EstadoOperacion.ABIERTA:
            self.estado = EstadoOperacion.CERRADA_TP
            eventos.append(EventoGestion(
                Evento.CIERRE, momento, precio,
                f"Todos los objetivos alcanzados. Operación cerrada. "
                f"Resultado total: {self.r_acumulado:+.2f}R.",
                self.r_acumulado, cierra_operacion=True))

        return eventos

    @property
    def abierta(self) -> bool:
        return self.estado is EstadoOperacion.ABIERTA

    def resumen_estado(self, precio_actual: float | None = None) -> dict:
        """Estado serializable de la operación para el panel/API en vivo."""
        r_flotante = self._r_en(precio_actual) * self.restante if precio_actual else None
        return {
            "direccion": self.direccion.value,
            "entrada": round(self.entrada, 2),
            "stop_actual": round(self.stop_actual, 2),
            "en_breakeven": self._en_breakeven,
            "restante": round(self.restante, 2),
            "r_asegurado": round(self.r_acumulado, 2),
            "r_flotante": round(r_flotante, 2) if r_flotante is not None else None,
            "estado": self.estado.value,
            "objetivos": [
                {"precio": round(n.precio, 2), "r": n.r_multiple,
                 "fraccion": n.fraccion, "alcanzado": n.alcanzado}
                for n in self.niveles
            ],
        }
