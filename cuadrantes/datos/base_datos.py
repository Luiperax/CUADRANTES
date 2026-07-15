"""
Capa de acceso a la base de datos SQLite.

SQLite se elige por ser un motor embebido, sin servidor, transaccional y muy
fiable, ideal para una aplicación de escritorio que debe conservar años de
histórico en un único fichero fácil de respaldar.

Este módulo se encarga de:
* Abrir la conexión y activar las claves foráneas.
* Crear el esquema completo si no existe (idempotente).
* Ofrecer utilidades de transacción y copia de seguridad.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# Sentencias de creación del esquema. Cada tabla incluye comentarios en castellano.
ESQUEMA_SQL = """
-- Trabajadores de seguridad privada.
CREATE TABLE IF NOT EXISTS trabajadores (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                     TEXT    NOT NULL UNIQUE,
    activo                     INTEGER NOT NULL DEFAULT 1,
    computo_mensual            REAL    NOT NULL DEFAULT 162.0,
    puestos_diurnos_permitidos TEXT    NOT NULL DEFAULT 'F1,F2,MO,EX',
    puestos_nocturnos_permitidos TEXT  NOT NULL DEFAULT 'F1,F2',
    puede_hacer_noches         INTEGER NOT NULL DEFAULT 1,
    fines_semana_exactos       INTEGER,
    es_jefe_equipo             INTEGER NOT NULL DEFAULT 0,
    prioridad_jefe             INTEGER NOT NULL DEFAULT 0,
    maximizar_dias             INTEGER NOT NULL DEFAULT 0,
    prefiere_turno_dia         INTEGER NOT NULL DEFAULT 0,
    prefiere_turno_noche       INTEGER NOT NULL DEFAULT 0,
    notas                      TEXT    NOT NULL DEFAULT ''
);

-- Ausencias de larga/media duración (vacaciones, bajas, permisos, formación...).
CREATE TABLE IF NOT EXISTS ausencias (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trabajador_id INTEGER NOT NULL REFERENCES trabajadores(id) ON DELETE CASCADE,
    tipo          TEXT    NOT NULL,
    fecha_inicio  TEXT    NOT NULL,
    fecha_fin     TEXT    NOT NULL,
    descripcion   TEXT    NOT NULL DEFAULT ''
);

-- Restricciones temporales por mes (días no disponibles, preferencias puntuales).
CREATE TABLE IF NOT EXISTS restricciones_temporales (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    trabajador_id        INTEGER NOT NULL REFERENCES trabajadores(id) ON DELETE CASCADE,
    anio                 INTEGER NOT NULL,
    mes                  INTEGER NOT NULL,
    dias_no_disponibles  TEXT    NOT NULL DEFAULT '',
    dias_prefiere_dia    TEXT    NOT NULL DEFAULT '',
    dias_prefiere_noche  TEXT    NOT NULL DEFAULT '',
    descripcion          TEXT    NOT NULL DEFAULT ''
);

-- Días festivos (se cubren como fin de semana).
CREATE TABLE IF NOT EXISTS festivos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT    NOT NULL UNIQUE,
    descripcion TEXT    NOT NULL DEFAULT ''
);

-- Incidencias extraordinarias registradas por mes.
CREATE TABLE IF NOT EXISTS incidencias (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    anio          INTEGER NOT NULL,
    mes           INTEGER NOT NULL,
    descripcion   TEXT    NOT NULL,
    trabajador_id INTEGER REFERENCES trabajadores(id) ON DELETE SET NULL,
    resuelta      INTEGER NOT NULL DEFAULT 0
);

-- Cabecera de cada cuadrante mensual.
CREATE TABLE IF NOT EXISTS cuadrantes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    anio              INTEGER NOT NULL,
    mes               INTEGER NOT NULL,
    empresa           TEXT    NOT NULL,
    sede              TEXT    NOT NULL,
    computo_mensual   REAL    NOT NULL,
    estado            TEXT    NOT NULL DEFAULT 'BORRADOR',
    version           INTEGER NOT NULL DEFAULT 1,
    fecha_generacion  TEXT,
    UNIQUE(anio, mes, version)
);

-- Asignaciones (una fila por trabajador y día del cuadrante).
CREATE TABLE IF NOT EXISTS asignaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cuadrante_id    INTEGER NOT NULL REFERENCES cuadrantes(id) ON DELETE CASCADE,
    trabajador_id   INTEGER NOT NULL REFERENCES trabajadores(id) ON DELETE CASCADE,
    dia             INTEGER NOT NULL,
    turno           TEXT,
    puesto          TEXT,
    ausencia        TEXT,
    es_cambio_manual INTEGER NOT NULL DEFAULT 0,
    UNIQUE(cuadrante_id, trabajador_id, dia)
);

-- Historial de cambios / registro de modificaciones (auditoría de seguridad).
CREATE TABLE IF NOT EXISTS historial_cambios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora    TEXT    NOT NULL,
    entidad       TEXT    NOT NULL,
    entidad_id    INTEGER,
    accion        TEXT    NOT NULL,
    detalle       TEXT    NOT NULL DEFAULT ''
);

-- Configuración de reglas (una única fila con clave 'principal').
CREATE TABLE IF NOT EXISTS configuracion (
    clave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);

-- Índices para acelerar las consultas más frecuentes.
CREATE INDEX IF NOT EXISTS idx_asig_cuadrante ON asignaciones(cuadrante_id);
CREATE INDEX IF NOT EXISTS idx_asig_trab      ON asignaciones(trabajador_id);
CREATE INDEX IF NOT EXISTS idx_ausencias_trab ON ausencias(trabajador_id);
CREATE INDEX IF NOT EXISTS idx_cuadrante_mes  ON cuadrantes(anio, mes);
"""


class BaseDatos:
    """Envoltorio de la conexión SQLite con utilidades de alto nivel."""

    def __init__(self, ruta: str | Path = "cuadrantes.db"):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.conexion = sqlite3.connect(str(self.ruta))
        self.conexion.row_factory = sqlite3.Row
        self.conexion.execute("PRAGMA foreign_keys = ON;")
        self.conexion.execute("PRAGMA journal_mode = WAL;")  # Mayor robustez ante fallos.
        # WAL permite que la aplicación de escritorio y la web (varios procesos)
        # compartan el mismo fichero: lectores concurrentes y un escritor. El
        # «busy_timeout» hace que, si ambos escriben a la vez, se espere en lugar de
        # fallar. Esto es lo que sincroniza ambas aplicaciones sobre la misma base.
        self.conexion.execute("PRAGMA busy_timeout = 5000;")
        self.crear_esquema()

    def crear_esquema(self) -> None:
        """Crea todas las tablas e índices si no existen (idempotente)."""
        self.conexion.executescript(ESQUEMA_SQL)
        self._migrar_esquema()
        self.conexion.commit()

    def _migrar_esquema(self) -> None:
        """Aplica migraciones ligeras para bases de datos creadas con versiones
        anteriores (añade columnas nuevas si faltan)."""
        columnas = {
            fila["name"]
            for fila in self.conexion.execute("PRAGMA table_info(trabajadores)").fetchall()
        }
        if "fines_semana_exactos" not in columnas:
            self.conexion.execute(
                "ALTER TABLE trabajadores ADD COLUMN fines_semana_exactos INTEGER"
            )
        if "es_jefe_equipo" not in columnas:
            self.conexion.execute(
                "ALTER TABLE trabajadores ADD COLUMN es_jefe_equipo INTEGER NOT NULL DEFAULT 0"
            )
        if "prioridad_jefe" not in columnas:
            self.conexion.execute(
                "ALTER TABLE trabajadores ADD COLUMN prioridad_jefe INTEGER NOT NULL DEFAULT 0"
            )
        if "maximizar_dias" not in columnas:
            self.conexion.execute(
                "ALTER TABLE trabajadores ADD COLUMN maximizar_dias INTEGER NOT NULL DEFAULT 0"
            )

    @contextmanager
    def transaccion(self):
        """Contexto transaccional: confirma al salir sin error, revierte si falla."""
        try:
            yield self.conexion
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def registrar_cambio(
        self, entidad: str, entidad_id: int | None, accion: str, detalle: str = ""
    ) -> None:
        """Anota una entrada en el historial de cambios (registro de modificaciones)."""
        self.conexion.execute(
            "INSERT INTO historial_cambios (fecha_hora, entidad, entidad_id, accion, detalle)"
            " VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), entidad, entidad_id, accion, detalle),
        )
        self.conexion.commit()

    def copia_seguridad(self, carpeta_destino: str | Path = "copias_seguridad") -> Path:
        """Realiza una copia de seguridad íntegra del fichero de base de datos.

        :return: ruta del fichero de copia generado.
        """
        carpeta = Path(carpeta_destino)
        carpeta.mkdir(parents=True, exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta / f"cuadrantes_{marca}.db"
        # Se usa la API de backup de SQLite para garantizar consistencia.
        with sqlite3.connect(str(destino)) as copia:
            self.conexion.backup(copia)
        return destino

    def cerrar(self) -> None:
        self.conexion.close()
