"""
Calendario de festivos de España, con soporte específico para Madrid.

Los festivos varían por comunidad autónoma y municipio, así que este módulo
calcula, para un año dado:

* Los **festivos nacionales** (fijos y los variables basados en la Semana Santa).
* Los **festivos autonómicos** (por defecto, Comunidad de Madrid).
* Los **festivos locales** (por defecto, Madrid capital: San Isidro y la Almudena).

El sitio de referencia (AV. SAN LUIS 77) está en Madrid capital, por lo que el
valor por defecto es Comunidad de Madrid + municipio de Madrid. El diseño permite
añadir otras comunidades ampliando ``FESTIVOS_AUTONOMICOS`` y ``FESTIVOS_LOCALES``.
"""

from __future__ import annotations

from datetime import date, timedelta


def domingo_de_pascua(anio: int) -> date:
    """Calcula el Domingo de Pascua (algoritmo de Gauss/computus gregoriano)."""
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ele = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ele) // 451
    mes = (h + ele - 7 * m + 114) // 31
    dia = ((h + ele - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _festivos_nacionales(anio: int) -> list[tuple[date, str]]:
    pascua = domingo_de_pascua(anio)
    viernes_santo = pascua - timedelta(days=2)
    return [
        (date(anio, 1, 1), "Año Nuevo"),
        (date(anio, 1, 6), "Epifanía del Señor (Reyes)"),
        (viernes_santo, "Viernes Santo"),
        (date(anio, 5, 1), "Fiesta del Trabajo"),
        (date(anio, 8, 15), "Asunción de la Virgen"),
        (date(anio, 10, 12), "Fiesta Nacional de España"),
        (date(anio, 11, 1), "Todos los Santos"),
        (date(anio, 12, 6), "Día de la Constitución"),
        (date(anio, 12, 8), "Inmaculada Concepción"),
        (date(anio, 12, 25), "Natividad del Señor (Navidad)"),
    ]


# Festivos autonómicos por comunidad. Se pueden añadir más comunidades aquí.
def _festivos_autonomicos(anio: int, comunidad: str) -> list[tuple[date, str]]:
    pascua = domingo_de_pascua(anio)
    jueves_santo = pascua - timedelta(days=3)
    if comunidad.strip().lower() in ("madrid", "comunidad de madrid"):
        return [
            (jueves_santo, "Jueves Santo"),
            (date(anio, 5, 2), "Día de la Comunidad de Madrid"),
        ]
    # Para otras comunidades, de momento solo Jueves Santo (habitual en la mayoría).
    return [(jueves_santo, "Jueves Santo")]


# Festivos locales por municipio.
def _festivos_locales(anio: int, municipio: str) -> list[tuple[date, str]]:
    if municipio.strip().lower() == "madrid":
        return [
            (date(anio, 5, 15), "San Isidro (local de Madrid)"),
            (date(anio, 11, 9), "Nuestra Señora de la Almudena (local de Madrid)"),
        ]
    return []


def festivos_del_anio(
    anio: int, comunidad: str = "Madrid", municipio: str = "Madrid"
) -> list[tuple[date, str]]:
    """Devuelve la lista de ``(fecha, descripción)`` de festivos del año.

    Incluye festivos nacionales, autonómicos y locales según la comunidad y el
    municipio indicados (por defecto, Comunidad de Madrid y Madrid capital).
    """
    festivos = (
        _festivos_nacionales(anio)
        + _festivos_autonomicos(anio, comunidad)
        + _festivos_locales(anio, municipio)
    )
    # Se eliminan duplicados por fecha (si algún festivo coincidiera) y se ordenan.
    unicos: dict[date, str] = {}
    for fecha, descripcion in festivos:
        unicos.setdefault(fecha, descripcion)
    return sorted(unicos.items())
