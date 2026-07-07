"""
Repositorios: conversión entre modelos de dominio y filas de SQLite.

Cada repositorio encapsula el acceso a una entidad, de forma que el resto de la
aplicación trabaja siempre con objetos de ``modelos.py`` y nunca con SQL crudo.
"""

from __future__ import annotations

from datetime import date

from ..config.configuracion import Configuracion
from ..config.constantes import EstadoCuadrante, Puesto, TipoAusencia, Turno
from .base_datos import BaseDatos
from .modelos import (
    Asignacion,
    Ausencia,
    Cuadrante,
    Festivo,
    Incidencia,
    RestriccionTemporal,
    Trabajador,
)


def _puestos_desde_texto(texto: str) -> set[Puesto]:
    return {Puesto(p) for p in texto.split(",") if p}


def _puestos_a_texto(puestos: set[Puesto]) -> str:
    # Se ordena para obtener una representación estable.
    return ",".join(p.value for p in sorted(puestos, key=lambda x: x.value))


def _dias_desde_texto(texto: str) -> set[int]:
    return {int(d) for d in texto.split(",") if d.strip()}


def _dias_a_texto(dias: set[int]) -> str:
    return ",".join(str(d) for d in sorted(dias))


class RepositorioTrabajadores:
    """Altas, bajas, modificaciones y consultas de trabajadores."""

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def _fila_a_modelo(self, fila) -> Trabajador:
        return Trabajador(
            id=fila["id"],
            nombre=fila["nombre"],
            activo=bool(fila["activo"]),
            computo_mensual=fila["computo_mensual"],
            puestos_diurnos_permitidos=_puestos_desde_texto(fila["puestos_diurnos_permitidos"]),
            puestos_nocturnos_permitidos=_puestos_desde_texto(fila["puestos_nocturnos_permitidos"]),
            puede_hacer_noches=bool(fila["puede_hacer_noches"]),
            fines_semana_exactos=fila["fines_semana_exactos"],
            es_jefe_equipo=bool(fila["es_jefe_equipo"]),
            prioridad_jefe=fila["prioridad_jefe"],
            prefiere_turno_dia=bool(fila["prefiere_turno_dia"]),
            prefiere_turno_noche=bool(fila["prefiere_turno_noche"]),
            notas=fila["notas"],
        )

    def guardar(self, trabajador: Trabajador) -> Trabajador:
        datos = (
            trabajador.nombre,
            int(trabajador.activo),
            trabajador.computo_mensual,
            _puestos_a_texto(trabajador.puestos_diurnos_permitidos),
            _puestos_a_texto(trabajador.puestos_nocturnos_permitidos),
            int(trabajador.puede_hacer_noches),
            trabajador.fines_semana_exactos,
            int(trabajador.es_jefe_equipo),
            trabajador.prioridad_jefe,
            int(trabajador.prefiere_turno_dia),
            int(trabajador.prefiere_turno_noche),
            trabajador.notas,
        )
        with self.bd.transaccion() as con:
            if trabajador.id is None:
                cur = con.execute(
                    "INSERT INTO trabajadores (nombre, activo, computo_mensual,"
                    " puestos_diurnos_permitidos, puestos_nocturnos_permitidos,"
                    " puede_hacer_noches, fines_semana_exactos, es_jefe_equipo,"
                    " prioridad_jefe, prefiere_turno_dia, prefiere_turno_noche, notas)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    datos,
                )
                trabajador.id = cur.lastrowid
                self.bd.registrar_cambio("trabajador", trabajador.id, "alta", trabajador.nombre)
            else:
                con.execute(
                    "UPDATE trabajadores SET nombre=?, activo=?, computo_mensual=?,"
                    " puestos_diurnos_permitidos=?, puestos_nocturnos_permitidos=?,"
                    " puede_hacer_noches=?, fines_semana_exactos=?, es_jefe_equipo=?,"
                    " prioridad_jefe=?, prefiere_turno_dia=?, prefiere_turno_noche=?, notas=?"
                    " WHERE id=?",
                    datos + (trabajador.id,),
                )
                self.bd.registrar_cambio("trabajador", trabajador.id, "modificacion", trabajador.nombre)
        return trabajador

    def obtener(self, trabajador_id: int) -> Trabajador | None:
        fila = self.bd.conexion.execute(
            "SELECT * FROM trabajadores WHERE id=?", (trabajador_id,)
        ).fetchone()
        return self._fila_a_modelo(fila) if fila else None

    def listar(self, solo_activos: bool = False) -> list[Trabajador]:
        sql = "SELECT * FROM trabajadores"
        if solo_activos:
            sql += " WHERE activo=1"
        sql += " ORDER BY id"
        return [self._fila_a_modelo(f) for f in self.bd.conexion.execute(sql).fetchall()]

    def eliminar(self, trabajador_id: int) -> None:
        with self.bd.transaccion() as con:
            con.execute("DELETE FROM trabajadores WHERE id=?", (trabajador_id,))
        self.bd.registrar_cambio("trabajador", trabajador_id, "baja")


class RepositorioAusencias:
    """Gestión de vacaciones, bajas, permisos y formación."""

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def guardar(self, ausencia: Ausencia) -> Ausencia:
        datos = (
            ausencia.trabajador_id,
            ausencia.tipo.value,
            ausencia.fecha_inicio.isoformat(),
            ausencia.fecha_fin.isoformat(),
            ausencia.descripcion,
        )
        with self.bd.transaccion() as con:
            if ausencia.id is None:
                cur = con.execute(
                    "INSERT INTO ausencias (trabajador_id, tipo, fecha_inicio, fecha_fin, descripcion)"
                    " VALUES (?, ?, ?, ?, ?)",
                    datos,
                )
                ausencia.id = cur.lastrowid
            else:
                con.execute(
                    "UPDATE ausencias SET trabajador_id=?, tipo=?, fecha_inicio=?, fecha_fin=?,"
                    " descripcion=? WHERE id=?",
                    datos + (ausencia.id,),
                )
        return ausencia

    def listar_por_mes(self, anio: int, mes: int) -> list[Ausencia]:
        """Devuelve las ausencias que se solapan con el mes indicado."""
        inicio_mes = date(anio, mes, 1).isoformat()
        # Primer día del mes siguiente.
        if mes == 12:
            fin_mes = date(anio + 1, 1, 1).isoformat()
        else:
            fin_mes = date(anio, mes + 1, 1).isoformat()
        filas = self.bd.conexion.execute(
            "SELECT * FROM ausencias WHERE fecha_inicio < ? AND fecha_fin >= ?",
            (fin_mes, inicio_mes),
        ).fetchall()
        return [self._fila_a_modelo(f) for f in filas]

    def listar_todas(self) -> list[Ausencia]:
        filas = self.bd.conexion.execute("SELECT * FROM ausencias ORDER BY fecha_inicio").fetchall()
        return [self._fila_a_modelo(f) for f in filas]

    def eliminar(self, ausencia_id: int) -> None:
        with self.bd.transaccion() as con:
            con.execute("DELETE FROM ausencias WHERE id=?", (ausencia_id,))

    def _fila_a_modelo(self, fila) -> Ausencia:
        return Ausencia(
            id=fila["id"],
            trabajador_id=fila["trabajador_id"],
            tipo=TipoAusencia(fila["tipo"]),
            fecha_inicio=date.fromisoformat(fila["fecha_inicio"]),
            fecha_fin=date.fromisoformat(fila["fecha_fin"]),
            descripcion=fila["descripcion"],
        )


class RepositorioRestricciones:
    """Restricciones temporales por mes."""

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def guardar(self, restriccion: RestriccionTemporal) -> RestriccionTemporal:
        datos = (
            restriccion.trabajador_id,
            restriccion.anio,
            restriccion.mes,
            _dias_a_texto(restriccion.dias_no_disponibles),
            _dias_a_texto(restriccion.dias_prefiere_dia),
            _dias_a_texto(restriccion.dias_prefiere_noche),
            restriccion.descripcion,
        )
        with self.bd.transaccion() as con:
            if restriccion.id is None:
                cur = con.execute(
                    "INSERT INTO restricciones_temporales (trabajador_id, anio, mes,"
                    " dias_no_disponibles, dias_prefiere_dia, dias_prefiere_noche, descripcion)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    datos,
                )
                restriccion.id = cur.lastrowid
            else:
                con.execute(
                    "UPDATE restricciones_temporales SET trabajador_id=?, anio=?, mes=?,"
                    " dias_no_disponibles=?, dias_prefiere_dia=?, dias_prefiere_noche=?,"
                    " descripcion=? WHERE id=?",
                    datos + (restriccion.id,),
                )
        return restriccion

    def listar_por_mes(self, anio: int, mes: int) -> list[RestriccionTemporal]:
        filas = self.bd.conexion.execute(
            "SELECT * FROM restricciones_temporales WHERE anio=? AND mes=?",
            (anio, mes),
        ).fetchall()
        return [self._fila_a_modelo(f) for f in filas]

    def _fila_a_modelo(self, fila) -> RestriccionTemporal:
        return RestriccionTemporal(
            id=fila["id"],
            trabajador_id=fila["trabajador_id"],
            anio=fila["anio"],
            mes=fila["mes"],
            dias_no_disponibles=_dias_desde_texto(fila["dias_no_disponibles"]),
            dias_prefiere_dia=_dias_desde_texto(fila["dias_prefiere_dia"]),
            dias_prefiere_noche=_dias_desde_texto(fila["dias_prefiere_noche"]),
            descripcion=fila["descripcion"],
        )


class RepositorioFestivos:
    """Días festivos del calendario."""

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def guardar(self, festivo: Festivo) -> Festivo:
        with self.bd.transaccion() as con:
            cur = con.execute(
                "INSERT OR REPLACE INTO festivos (fecha, descripcion) VALUES (?, ?)",
                (festivo.fecha.isoformat(), festivo.descripcion),
            )
            festivo.id = cur.lastrowid
        return festivo

    def listar_por_mes(self, anio: int, mes: int) -> list[Festivo]:
        prefijo = f"{anio:04d}-{mes:02d}-%"
        filas = self.bd.conexion.execute(
            "SELECT * FROM festivos WHERE fecha LIKE ? ORDER BY fecha", (prefijo,)
        ).fetchall()
        return [
            Festivo(id=f["id"], fecha=date.fromisoformat(f["fecha"]), descripcion=f["descripcion"])
            for f in filas
        ]

    def eliminar(self, festivo_id: int) -> None:
        with self.bd.transaccion() as con:
            con.execute("DELETE FROM festivos WHERE id=?", (festivo_id,))


class RepositorioIncidencias:
    """Incidencias extraordinarias mensuales."""

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def guardar(self, incidencia: Incidencia) -> Incidencia:
        datos = (
            incidencia.anio,
            incidencia.mes,
            incidencia.descripcion,
            incidencia.trabajador_id,
            int(incidencia.resuelta),
        )
        with self.bd.transaccion() as con:
            if incidencia.id is None:
                cur = con.execute(
                    "INSERT INTO incidencias (anio, mes, descripcion, trabajador_id, resuelta)"
                    " VALUES (?, ?, ?, ?, ?)",
                    datos,
                )
                incidencia.id = cur.lastrowid
            else:
                con.execute(
                    "UPDATE incidencias SET anio=?, mes=?, descripcion=?, trabajador_id=?,"
                    " resuelta=? WHERE id=?",
                    datos + (incidencia.id,),
                )
        return incidencia

    def listar_por_mes(self, anio: int, mes: int) -> list[Incidencia]:
        filas = self.bd.conexion.execute(
            "SELECT * FROM incidencias WHERE anio=? AND mes=?", (anio, mes)
        ).fetchall()
        return [
            Incidencia(
                id=f["id"], anio=f["anio"], mes=f["mes"], descripcion=f["descripcion"],
                trabajador_id=f["trabajador_id"], resuelta=bool(f["resuelta"]),
            )
            for f in filas
        ]


class RepositorioCuadrantes:
    """Persistencia de cuadrantes completos con sus asignaciones."""

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def guardar(self, cuadrante: Cuadrante) -> Cuadrante:
        """Inserta o actualiza el cuadrante y todas sus asignaciones."""
        with self.bd.transaccion() as con:
            if cuadrante.id is None:
                cur = con.execute(
                    "INSERT INTO cuadrantes (anio, mes, empresa, sede, computo_mensual, estado,"
                    " version, fecha_generacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        cuadrante.anio, cuadrante.mes, cuadrante.empresa, cuadrante.sede,
                        cuadrante.computo_mensual, cuadrante.estado.value, cuadrante.version,
                        cuadrante.fecha_generacion.isoformat() if cuadrante.fecha_generacion else None,
                    ),
                )
                cuadrante.id = cur.lastrowid
            else:
                con.execute(
                    "UPDATE cuadrantes SET estado=?, computo_mensual=?, fecha_generacion=?"
                    " WHERE id=?",
                    (
                        cuadrante.estado.value, cuadrante.computo_mensual,
                        cuadrante.fecha_generacion.isoformat() if cuadrante.fecha_generacion else None,
                        cuadrante.id,
                    ),
                )
                con.execute("DELETE FROM asignaciones WHERE cuadrante_id=?", (cuadrante.id,))

            for asignacion in cuadrante.asignaciones.values():
                con.execute(
                    "INSERT INTO asignaciones (cuadrante_id, trabajador_id, dia, turno, puesto,"
                    " ausencia, es_cambio_manual) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        cuadrante.id, asignacion.trabajador_id, asignacion.dia,
                        asignacion.turno.value if asignacion.turno else None,
                        asignacion.puesto.value if asignacion.puesto else None,
                        asignacion.ausencia.value if asignacion.ausencia else None,
                        int(asignacion.es_cambio_manual),
                    ),
                )
        self.bd.registrar_cambio("cuadrante", cuadrante.id, "guardado",
                                 f"{cuadrante.mes:02d}/{cuadrante.anio} v{cuadrante.version}")
        return cuadrante

    def cargar(self, cuadrante_id: int) -> Cuadrante | None:
        fila = self.bd.conexion.execute(
            "SELECT * FROM cuadrantes WHERE id=?", (cuadrante_id,)
        ).fetchone()
        if not fila:
            return None
        cuadrante = Cuadrante(
            id=fila["id"], anio=fila["anio"], mes=fila["mes"], empresa=fila["empresa"],
            sede=fila["sede"], computo_mensual=fila["computo_mensual"],
            estado=EstadoCuadrante(fila["estado"]), version=fila["version"],
            fecha_generacion=date.fromisoformat(fila["fecha_generacion"]) if fila["fecha_generacion"] else None,
        )
        filas = self.bd.conexion.execute(
            "SELECT * FROM asignaciones WHERE cuadrante_id=? ORDER BY trabajador_id, dia",
            (cuadrante_id,),
        ).fetchall()
        trabajadores_vistos: list[int] = []
        for a in filas:
            asignacion = Asignacion(
                trabajador_id=a["trabajador_id"], dia=a["dia"],
                turno=Turno(a["turno"]) if a["turno"] else None,
                puesto=Puesto(a["puesto"]) if a["puesto"] else None,
                ausencia=TipoAusencia(a["ausencia"]) if a["ausencia"] else None,
                es_cambio_manual=bool(a["es_cambio_manual"]),
            )
            cuadrante.establecer(asignacion)
            if a["trabajador_id"] not in trabajadores_vistos:
                trabajadores_vistos.append(a["trabajador_id"])
        cuadrante.trabajadores_ids = trabajadores_vistos
        return cuadrante

    def ultima_version(self, anio: int, mes: int) -> Cuadrante | None:
        fila = self.bd.conexion.execute(
            "SELECT id FROM cuadrantes WHERE anio=? AND mes=? ORDER BY version DESC LIMIT 1",
            (anio, mes),
        ).fetchone()
        return self.cargar(fila["id"]) if fila else None

    def eliminar(self, cuadrante_id: int) -> None:
        """Elimina un cuadrante del historial (y sus asignaciones en cascada)."""
        with self.bd.transaccion() as con:
            con.execute("DELETE FROM cuadrantes WHERE id=?", (cuadrante_id,))
        self.bd.registrar_cambio("cuadrante", cuadrante_id, "eliminado")

    def listar_cabeceras(self) -> list[dict]:
        """Lista ligera de cuadrantes (para la barra lateral)."""
        filas = self.bd.conexion.execute(
            "SELECT id, anio, mes, estado, version FROM cuadrantes ORDER BY anio DESC, mes DESC, version DESC"
        ).fetchall()
        return [dict(f) for f in filas]

    def cargar_historico(self, anio: int, mes: int, meses_atras: int) -> list[Cuadrante]:
        """Carga los cuadrantes de los ``meses_atras`` meses anteriores al indicado."""
        objetivo = anio * 12 + (mes - 1)
        resultado: list[Cuadrante] = []
        for cabecera in self.listar_cabeceras():
            clave = cabecera["anio"] * 12 + (cabecera["mes"] - 1)
            if objetivo - meses_atras <= clave < objetivo:
                cuad = self.cargar(cabecera["id"])
                if cuad:
                    resultado.append(cuad)
        return resultado


class RepositorioConfiguracion:
    """Persistencia de la configuración de reglas."""

    CLAVE = "principal"

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def cargar(self) -> Configuracion:
        fila = self.bd.conexion.execute(
            "SELECT valor FROM configuracion WHERE clave=?", (self.CLAVE,)
        ).fetchone()
        if fila:
            return Configuracion.desde_json(fila["valor"])
        # Si no existe, se crea con los valores por defecto.
        config = Configuracion()
        self.guardar(config)
        return config

    def guardar(self, config: Configuracion) -> None:
        with self.bd.transaccion() as con:
            con.execute(
                "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
                (self.CLAVE, config.a_json()),
            )
        self.bd.registrar_cambio("configuracion", None, "guardado")
