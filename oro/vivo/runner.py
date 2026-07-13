"""Bucle de ejecución en vivo.

En cada ciclo:

1. Refresca los datos de precio y calcula el estado de mercado (ATR, sesión).
2. Consulta el sentimiento de prensa y el calendario macro (riesgo de noticia).
3. **Gestiona las operaciones abiertas** y notifica sus salidas (TP, break-even,
   stop, cierre).
4. Si procede (tope diario de 2–4 no alcanzado y hay hueco), busca una **nueva
   entrada A+** y la notifica.

El bucle está pensado para ejecutarse en la máquina del usuario (o un servidor).
Cada evento se envía por los canales configurados (Telegram, push, email…).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import List, Optional

from ..config import ConfiguracionSistema, cargar_configuracion
from ..datos import ProveedorDatos, ProveedorYahoo
from ..dominio import MarketSnapshot, Signal, sesion_de
from ..indicadores import atr as _atr
from ..notificaciones import Notificador, NotificadorConsola
from ..notificaciones.base import Evento
from ..senales import MotorSenales
from ..sentimiento import AnalizadorSentimiento, ContextoInformativo
from .gestor import GestorOperaciones


@dataclass(slots=True)
class CicloResultado:
    momento: datetime
    precio: float
    resumen_sentimiento: str
    eventos_salida: List[str] = field(default_factory=list)
    nueva_senal: Optional[Signal] = None
    motivo_sin_entrada: str = ""
    abiertas: int = 0
    senales_hoy: int = 0


class RunnerVivo:
    def __init__(
        self,
        cfg: Optional[ConfiguracionSistema] = None,
        proveedor: Optional[ProveedorDatos] = None,
        notificador: Optional[Notificador] = None,
        analizador: Optional[AnalizadorSentimiento] = None,
        modelo=None,
        max_concurrentes: int = 2,
        usar_sentimiento: bool = True,
    ) -> None:
        self.cfg = cfg or cargar_configuracion()
        self.proveedor = proveedor or ProveedorYahoo(timeframe=self.cfg.timeframe)
        self.notificador = notificador or NotificadorConsola()
        self.analizador = analizador or AnalizadorSentimiento()
        self.motor = MotorSenales(self.cfg, modelo=modelo)
        self.max_concurrentes = max_concurrentes
        self.usar_sentimiento = usar_sentimiento

        self.abiertas: List[GestorOperaciones] = []
        self._senales_hoy = 0
        self._fecha: Optional[date] = None

    # ---- un ciclo del bucle ----
    def ciclo(self, velas: int = 500) -> CicloResultado:
        if hasattr(self.proveedor, "refrescar"):
            try:
                self.proveedor.refrescar()
            except Exception:  # noqa: BLE001 — un fallo de red no debe romper el bucle.
                pass
        df = self.proveedor.historico(velas)
        ultima = df.iloc[-1]
        momento = ultima.name.to_pydatetime()
        precio = float(ultima["close"])
        self._reset_diario(momento)

        # Contexto informativo (sentimiento + riesgo de noticia).
        if self.usar_sentimiento:
            contexto = self.analizador.analizar(momento)
        else:
            contexto = ContextoInformativo(None, 0, 0, False)

        resultado = CicloResultado(
            momento=momento, precio=precio,
            resumen_sentimiento=contexto.resumen(),
        )

        # 1) Gestionar salidas de las operaciones abiertas.
        for gestor in list(self.abiertas):
            for ev in gestor.actualizar(precio, momento):
                self._notificar_evento(ev, gestor)
                resultado.eventos_salida.append(ev.mensaje)
            if not gestor.abierta:
                self.abiertas.remove(gestor)
        resultado.abiertas = len(self.abiertas)

        # 2) ¿Buscar nueva entrada?
        if len(self.abiertas) >= self.max_concurrentes:
            resultado.motivo_sin_entrada = "Máximo de operaciones simultáneas alcanzado."
        elif self._senales_hoy >= self.cfg.riesgo.operaciones_max_dia:
            resultado.motivo_sin_entrada = "Tope diario de señales alcanzado."
        else:
            snapshot = self._snapshot(df, momento, precio, contexto)
            analisis = self.motor.analizar(df, snapshot)
            if analisis.hay_operacion and analisis.signal is not None:
                gestor = GestorOperaciones(analisis.signal, entrada_real=precio)
                self.abiertas.append(gestor)
                self._senales_hoy += 1
                self.notificador.notificar_senal(analisis.signal)
                resultado.nueva_senal = analisis.signal
            else:
                resultado.motivo_sin_entrada = "; ".join(analisis.motivos_no) or analisis.mensaje

        resultado.senales_hoy = self._senales_hoy
        resultado.abiertas = len(self.abiertas)
        return resultado

    # ---- bucle continuo (para la máquina del usuario) ----
    def ejecutar(self, intervalo_seg: int = 900, max_ciclos: Optional[int] = None) -> None:
        """Ejecuta el bucle indefinidamente (o ``max_ciclos`` veces).

        ``intervalo_seg`` por defecto 15 min (coincide con el timeframe M15).
        """
        import time

        ciclos = 0
        print(f"▶ Runner en vivo iniciado (intervalo {intervalo_seg}s, "
              f"máx {self.cfg.riesgo.operaciones_max_dia} señales/día).")
        while max_ciclos is None or ciclos < max_ciclos:
            try:
                r = self.ciclo()
                print(f"[{r.momento:%Y-%m-%d %H:%M}] oro={r.precio:.2f} | "
                      f"{r.resumen_sentimiento} | abiertas={r.abiertas} señales_hoy={r.senales_hoy}")
                if r.nueva_senal:
                    print("   → NUEVA ENTRADA:", r.nueva_senal.resumen())
                for ev in r.eventos_salida:
                    print("   → SALIDA:", ev)
            except Exception as e:  # noqa: BLE001 — el bucle no debe caerse.
                print("   ! error en el ciclo:", type(e).__name__, str(e)[:80])
            ciclos += 1
            if max_ciclos is not None and ciclos >= max_ciclos:
                break
            time.sleep(intervalo_seg)

    # ---- helpers ----
    def _reset_diario(self, momento: datetime) -> None:
        hoy = momento.date()
        if self._fecha != hoy:
            self._fecha = hoy
            self._senales_hoy = 0

    def _snapshot(self, df, momento, precio, contexto: ContextoInformativo) -> MarketSnapshot:
        atr_val = float(_atr(df, 14).iloc[-1])
        spread = float(df.iloc[-1].get("spread", 0.2))
        return MarketSnapshot(
            momento=momento, precio=precio, spread=spread, atr=atr_val,
            sesion=sesion_de(momento),
            sentimiento=contexto.sentimiento,
            riesgo_noticia_alta=contexto.riesgo_noticia_alta,
        )

    def _notificar_evento(self, ev, gestor: GestorOperaciones) -> None:
        titulos = {
            Evento.TP_ALCANZADO: "🎯 Objetivo alcanzado — XAU/USD",
            Evento.MOVER_STOP: "🛡 Mover stop a break-even — XAU/USD",
            Evento.CIERRE: "🏁 Cierre de operación — XAU/USD",
        }
        titulo = titulos.get(ev.tipo, "Actualización — XAU/USD")
        cuerpo = f"{ev.mensaje}\n\nDirección: {gestor.direccion.value.upper()} | Entrada: {gestor.entrada:.2f}"
        self.notificador.enviar(titulo, cuerpo, ev.tipo)
