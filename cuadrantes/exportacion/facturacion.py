"""
Exportación del CUADRANTE DE FACTURACIÓN (formato del cliente).

A diferencia del cuadrante operativo, la hoja de facturación reorganiza el mes
por SERVICIO / orden de trabajo (OT): cada puesto es un servicio que se factura
por separado al cliente. Para cada servicio se listan los empleados que lo han
cubierto, con su hora de entrada y de salida por día, las horas por jornada
(12 h) y los totales, más el total diario del servicio y el total general.

Correspondencia puesto -> servicio (según el cuadrante real de NATURGY):

* F1 -> RECEPCIÓN 24 H            (MT 7-19 / TN 19-7)
* F2 -> GARITA 24 H              (MT 7-19 / TN 19-7)
* MO -> MÓVIL/RESPONSABLE 7 a 19 (solo mañana)
* EX -> EXPLANADA 6 a 18         (solo mañana, horario 6-18)
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter

from ..config.constantes import NOMBRES_MES, Puesto, TipoAusencia, Turno
from ..datos.modelos import Cuadrante, Trabajador
from ..dominio.calendario import CalendarioMes

# Servicios (OT) en el orden en que aparecen en la hoja del cliente.
_SERVICIOS = [
    (Puesto.F1, "01CE000579287511", "RECEPCIÓN 24 H"),
    (Puesto.F2, "01CE000579287521", "GARITA 24 H VSA"),
    (Puesto.MO, "01CE000579287531", "MÓVIL/RESPONSABLE VSA DE 7 a 19"),
    (Puesto.EX, "01CE000579287541", "EXPLANADA VSA de 6 a 18"),
]

_COMPUTO = 162.0

# --- Estilos ---------------------------------------------------------------
_FINO = Side(style="thin", color="808080")
_BORDE = Border(left=_FINO, right=_FINO, top=_FINO, bottom=_FINO)
_CENTRO = Alignment(horizontal="center", vertical="center")
_IZQ = Alignment(horizontal="left", vertical="center")
_EDIT = Protection(locked=False)

_AZUL = "9DC3E6"        # fin de semana
_PEACH = "FCE4D6"       # fila SUMA
_AMAR = "FFF2CC"        # totales
_CYAN = "00B0F0"        # vacaciones (V)
_GRIS = "D9D9D9"        # cabeceras de datos
_NEGRO = "000000"

_F_NORM = Font(name="Arial", size=8)
_F_NEG = Font(name="Arial", size=8, bold=True)
_F_PEQ = Font(name="Arial", size=7)
_F_TIT = Font(name="Arial", size=11, bold=True)
_F_OT = Font(name="Arial", size=9, bold=True, color="FFFFFF")
_F_OTCOD = Font(name="Arial", size=9, bold=True, color="FF0000")


def _relleno(color):
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def _entrada_salida(turno: Turno, puesto: Puesto) -> tuple[int, int]:
    """Hora de entrada y de salida según turno y puesto."""
    if puesto is Puesto.EX:      # Explanada 6-18 (siempre de mañana).
        return 6, 18
    if turno is Turno.NOCHE:     # Noche 19-7.
        return 19, 7
    return 7, 19                 # Mañana 7-19.


def construir_datos_facturacion(cuadrante: Cuadrante, trabajadores: dict[int, Trabajador],
                                calendario: CalendarioMes) -> dict:
    """Estructura lógica de la facturación (la usan el Excel y la vista en pantalla).

    Devuelve ``{'servicios': [...], 'total_general_dia': [...], 'total_general': ...}``.
    Cada servicio: ``{'codigo','nombre','empleados','totales_dia','total'}``.
    Cada empleado: ``{'nombre','celdas':[{entrada,salida,suma,vac,finde}...],'total','dif'}``.
    """
    dias = calendario.dias
    ids = cuadrante.trabajadores_ids or list(trabajadores.keys())
    servicios = []
    for puesto, codigo, nombre in _SERVICIOS:
        empleados = []
        for tid in ids:
            if not any((a := cuadrante.obtener(tid, d)) and a.es_trabajo and a.puesto is puesto
                       for d in dias):
                continue
            celdas, total = [], 0
            for dia in dias:
                a = cuadrante.obtener(tid, dia)
                cel = {"entrada": "", "salida": "", "suma": "", "vac": False,
                       "finde": calendario.es_fin_de_semana(dia)}
                if a and a.es_trabajo and a.puesto is puesto:
                    e, s = _entrada_salida(a.turno, puesto)
                    cel["entrada"], cel["salida"], cel["suma"] = e, s, 12
                    total += 12
                elif a and a.ausencia is TipoAusencia.VACACIONES:
                    cel["entrada"] = cel["salida"] = "V"
                    cel["vac"] = True
                celdas.append(cel)
            nombre_t = trabajadores[tid].nombre if tid in trabajadores else str(tid)
            empleados.append({"id": tid, "nombre": nombre_t, "celdas": celdas,
                              "total": total, "dif": total - _COMPUTO})
        tot_dia = []
        for dia in dias:
            h = sum(12 for e in empleados
                    if (a := cuadrante.obtener(e["id"], dia)) and a.es_trabajo and a.puesto is puesto)
            tot_dia.append(h)
        servicios.append({"codigo": codigo, "nombre": nombre, "puesto": puesto,
                          "empleados": empleados, "totales_dia": tot_dia, "total": sum(tot_dia)})
    tg = []
    for dia in dias:
        h = sum(12 for tid in ids if (a := cuadrante.obtener(tid, dia)) and a.es_trabajo)
        tg.append(h)
    return {"servicios": servicios, "total_general_dia": tg, "total_general": sum(tg)}


class ExportadorFacturacion:
    """Genera el cuadrante de facturación en Excel, agrupado por servicio."""

    def __init__(self, cuadrante: Cuadrante, trabajadores: dict[int, Trabajador],
                 festivos: set | None = None):
        self.cuadrante = cuadrante
        self.trabajadores = trabajadores
        self.calendario = CalendarioMes(cuadrante.anio, cuadrante.mes, festivos or set())
        self.n_dias = self.calendario.numero_dias
        self.col_dia0 = 3                       # primera columna de día (C)
        self.col_tot = self.col_dia0 + self.n_dias      # TOTALES
        self.col_dif = self.col_tot + 1                 # diferencia / etiquetas

    # ------------------------------------------------------------------
    def exportar(self, ruta: str | Path) -> Path:
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Facturación"
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
        hoja.page_setup.orientation = "landscape"
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0

        fila = self._cabecera(hoja)
        for puesto, codigo, nombre in _SERVICIOS:
            fila = self._bloque_servicio(hoja, fila, puesto, codigo, nombre)
            fila += 1
        self._total_general(hoja, fila)
        self._anchos(hoja)

        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        libro.save(str(ruta))
        return ruta

    # ------------------------------------------------------------------
    def _cel(self, hoja, fila, col, valor="", fuente=_F_NORM, relleno=None,
             alin=_CENTRO, borde=True):
        c = hoja.cell(row=fila, column=col, value=valor)
        c.font = fuente
        c.alignment = alin
        c.protection = _EDIT
        if borde:
            c.border = _BORDE
        if relleno:
            c.fill = _relleno(relleno)
        return c

    def _cabecera(self, hoja) -> int:
        mes = NOMBRES_MES[self.cuadrante.mes].upper()
        self._cel(hoja, 1, 1, "OK - REPUESTA", fuente=_F_PEQ, borde=False)
        self._cel(hoja, 1, self.col_tot, "Código Documento", fuente=_F_PEQ, borde=False)
        self._cel(hoja, 2, self.col_tot, "MD-ES-SISVG-VA-03", fuente=_F_PEQ, borde=False)
        self._cel(hoja, 3, self.col_tot, "Edición: 01", fuente=_F_PEQ, borde=False)
        # Bloque CLIENTE / CENTRO / MES.
        self._cel(hoja, 2, 3, "CLIENTE:", fuente=_F_NEG, relleno=_GRIS)
        self._cel(hoja, 2, 5, "NATURGY", fuente=_F_TIT)
        self._cel(hoja, 3, 3, "CENTRO:", fuente=_F_NEG, relleno=_GRIS)
        self._cel(hoja, 3, 5, "EDIFICIO AVENIDA DE SAN LUIS", fuente=_F_NEG)
        self._cel(hoja, 2, 9, "CD. CENTRO:", fuente=_F_NEG, relleno=_GRIS)
        self._cel(hoja, 3, 9, "MES:", fuente=_F_NEG, relleno=_GRIS)
        self._cel(hoja, 3, 11, f"{mes} {self.cuadrante.anio}", fuente=_F_TIT)
        self._cel(hoja, 4, 9, "SIN ARMA", fuente=_F_NEG, relleno=_GRIS)
        return 6

    def _fila_dias(self, hoja, fila) -> int:
        """Escribe la fila de letras de día y la de números. Devuelve la siguiente."""
        self._cel(hoja, fila, 1, "EMPLEADO", fuente=_F_NEG, relleno=_GRIS, alin=_IZQ)
        self._cel(hoja, fila + 1, self.col_tot, "TOTALES", fuente=_F_NEG, relleno=_GRIS)
        for dia in self.calendario.dias:
            col = self.col_dia0 + dia - 1
            finde = self.calendario.es_fin_de_semana(dia)
            rel = _AZUL if finde else None
            self._cel(hoja, fila, col, self.calendario.letra_dia(dia), fuente=_F_NEG, relleno=rel)
            self._cel(hoja, fila + 1, col, dia, fuente=_F_NEG, relleno=rel)
        return fila + 2

    def _asignacion(self, tid, dia):
        return self.cuadrante.obtener(tid, dia)

    def _empleados_de(self, puesto: Puesto) -> list[int]:
        """Ids de trabajadores con al menos un turno en ese puesto, por orden de plantilla."""
        ids = self.cuadrante.trabajadores_ids or list(self.trabajadores.keys())
        con_puesto = []
        for tid in ids:
            for dia in self.calendario.dias:
                a = self._asignacion(tid, dia)
                if a and a.es_trabajo and a.puesto is puesto:
                    con_puesto.append(tid)
                    break
        return con_puesto

    def _bloque_servicio(self, hoja, fila, puesto, codigo, nombre) -> int:
        fila = self._fila_dias(hoja, fila)
        # Cabecera negra del servicio (código en rojo + nombre en blanco).
        self._cel(hoja, fila, 1, codigo, fuente=_F_OTCOD, relleno=_NEGRO, alin=_IZQ)
        c = self._cel(hoja, fila, 2, nombre, fuente=_F_OT, relleno=_NEGRO, alin=_IZQ)
        for col in range(3, self.col_dif + 1):
            self._cel(hoja, fila, col, "", relleno=_NEGRO)
        fila += 1

        empleados = self._empleados_de(puesto)
        for tid in empleados:
            fila = self._filas_empleado(hoja, fila, tid, puesto)

        # Total diario del servicio.
        self._cel(hoja, fila, 1, "", borde=False)
        self._cel(hoja, fila, 2, "", borde=False)
        total_serv = 0
        for dia in self.calendario.dias:
            col = self.col_dia0 + dia - 1
            horas = 0
            for tid in empleados:
                a = self._asignacion(tid, dia)
                if a and a.es_trabajo and a.puesto is puesto:
                    horas += 12
            total_serv += horas
            self._cel(hoja, fila, col, horas or "", fuente=_F_NEG, relleno=_AMAR)
        self._cel(hoja, fila, self.col_tot, total_serv, fuente=_F_NEG, relleno=_AMAR)
        return fila + 1

    def _filas_empleado(self, hoja, fila, tid, puesto) -> int:
        nombre = self.trabajadores[tid].nombre if tid in self.trabajadores else str(tid)
        f_ent, f_sal, f_sum = fila, fila + 1, fila + 2
        # Nombre combinado sobre las tres filas.
        hoja.merge_cells(start_row=f_ent, start_column=1, end_row=f_sum, end_column=1)
        self._cel(hoja, f_ent, 1, nombre, fuente=_F_NEG, alin=_IZQ)
        self._cel(hoja, f_ent, 2, "HORA DE ENTRADA", fuente=_F_PEQ, alin=_IZQ)
        self._cel(hoja, f_sal, 2, "HORA DE SALIDA", fuente=_F_PEQ, alin=_IZQ)
        self._cel(hoja, f_sum, 2, "SUMA", fuente=_F_PEQ, alin=_IZQ)

        total = 0
        for dia in self.calendario.dias:
            col = self.col_dia0 + dia - 1
            finde = self.calendario.es_fin_de_semana(dia)
            rel_base = _AZUL if finde else None
            a = self._asignacion(tid, dia)
            ent = sal = suma = ""
            rel_ent = rel_sal = rel_base
            rel_sum = _PEACH
            if a and a.es_trabajo and a.puesto is puesto:
                e, s = _entrada_salida(a.turno, puesto)
                ent, sal, suma = e, s, 12
                total += 12
            elif a and a.ausencia is TipoAusencia.VACACIONES:
                ent = sal = "V"
                rel_ent = rel_sal = _CYAN
                rel_sum = rel_base
            self._cel(hoja, f_ent, col, ent, fuente=_F_NEG, relleno=rel_ent)
            self._cel(hoja, f_sal, col, sal, fuente=_F_NEG, relleno=rel_sal)
            self._cel(hoja, f_sum, col, suma, fuente=_F_PEQ, relleno=rel_sum)
        # Etiquetas y totales a la derecha.
        self._cel(hoja, f_ent, self.col_dif, "HORAS", fuente=_F_PEQ, borde=False)
        self._cel(hoja, f_sal, self.col_dif, "EXTRAS", fuente=_F_PEQ, borde=False)
        self._cel(hoja, f_sum, self.col_tot, total or "", fuente=_F_NEG, relleno=_AMAR)
        self._cel(hoja, f_sum, self.col_dif, f"{total - _COMPUTO:.2f}".replace(".", ","),
                  fuente=_F_NEG, borde=False)
        return f_sum + 1

    def _total_general(self, hoja, fila) -> None:
        self._cel(hoja, fila, 1, "TOTAL GENERAL", fuente=_F_NEG, relleno=_AMAR, alin=_IZQ)
        self._cel(hoja, fila, 2, "", relleno=_AMAR)
        total_mes = 0
        for dia in self.calendario.dias:
            col = self.col_dia0 + dia - 1
            horas = 0
            for tid in (self.cuadrante.trabajadores_ids or self.trabajadores.keys()):
                a = self._asignacion(tid, dia)
                if a and a.es_trabajo:
                    horas += 12
            total_mes += horas
            self._cel(hoja, fila, col, horas, fuente=_F_NEG, relleno=_AMAR)
        self._cel(hoja, fila, self.col_tot, total_mes, fuente=_F_NEG, relleno=_AMAR)

    def _anchos(self, hoja) -> None:
        hoja.column_dimensions["A"].width = 28
        hoja.column_dimensions["B"].width = 14
        for dia in self.calendario.dias:
            hoja.column_dimensions[get_column_letter(self.col_dia0 + dia - 1)].width = 3.5
        hoja.column_dimensions[get_column_letter(self.col_tot)].width = 8
        hoja.column_dimensions[get_column_letter(self.col_dif)].width = 9
