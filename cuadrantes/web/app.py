"""
Versión web (móvil y escritorio) del Generador de Cuadrantes.

Reutiliza íntegramente el motor de optimización, la base de datos, la auditoría y
los exportadores del paquete ``cuadrantes``; solo cambia la capa de presentación,
que aquí es un servidor web ligero (FastAPI) con páginas adaptadas al móvil.

Así, el mismo sistema puede usarse desde el navegador de un teléfono: basta con
tener el servidor en marcha (en un ordenador de la red o en un alojamiento) y
abrir su dirección desde el móvil.

Nota técnica: cada petición abre su propia conexión a la base de datos (mediante
una dependencia de FastAPI) porque SQLite asocia cada conexión a un hilo y el
servidor atiende las peticiones en un grupo de hilos. Así se evita compartir una
conexión entre hilos distintos.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config.constantes import NOMBRES_MES, Puesto, TipoAusencia
from ..datos.datos_iniciales import cargar_plantilla_ejemplo, sincronizar_equipo
from ..datos.modelos import Ausencia, Trabajador
from ..dominio.calendario import CalendarioMes
from ..dominio.computos import calcular_resumenes
from ..rutas import ruta_base_datos
from ..servicio import ServicioCuadrantes

_BASE = Path(__file__).parent
# Ruta compartida con la aplicación de escritorio (misma base de datos).
_RUTA_BD = str(ruta_base_datos())


def crear_app(ruta_bd: str = _RUTA_BD) -> FastAPI:
    """Crea y configura la aplicación web."""
    app = FastAPI(title="Cuadrantes de Seguridad Privada")
    plantillas = Jinja2Templates(directory=str(_BASE / "plantillas"))
    app.mount("/estaticos", StaticFiles(directory=str(_BASE / "estaticos")), name="estaticos")
    plantillas.env.filters["mes"] = lambda m: NOMBRES_MES[m].capitalize()

    # Inicialización única: crea el esquema y carga el equipo si la BD está vacía.
    arranque = ServicioCuadrantes(ruta_bd)
    cargar_plantilla_ejemplo(arranque)
    arranque.cerrar()

    def obtener_servicio():
        """Dependencia: una conexión/servicio por petición, cerrada al terminar."""
        servicio = ServicioCuadrantes(ruta_bd)
        try:
            yield servicio
        finally:
            servicio.cerrar()

    def _ctx(request: Request, plantilla: str, **extra):
        """Renderiza una plantilla (compatible con la API actual de Starlette)."""
        contexto = {"nombres_mes": NOMBRES_MES}
        contexto.update(extra)
        return plantillas.TemplateResponse(request=request, name=plantilla, context=contexto)

    # ------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def panel(request: Request, srv: ServicioCuadrantes = Depends(obtener_servicio)):
        cabeceras = srv.cuadrantes.listar_cabeceras()
        hoy = date.today()
        mes_sig = hoy.month % 12 + 1
        anio_sig = hoy.year + (1 if hoy.month == 12 else 0)
        return _ctx(request, "panel.html",
             cabeceras=cabeceras, mes_sugerido=mes_sig, anio_sugerido=anio_sig,
            n_trabajadores=len(srv.trabajadores.listar(solo_activos=True)))

    @app.post("/generar")
    def generar(mes: int = Form(...), anio: int = Form(...),
                srv: ServicioCuadrantes = Depends(obtener_servicio)):
        srv.generar(anio, mes)
        cuad = srv.cuadrantes.ultima_version(anio, mes)
        return RedirectResponse(f"/cuadrante/{cuad.id}", status_code=303)

    # ------------------------------------------------------------------
    @app.get("/cuadrante/{cuadrante_id}", response_class=HTMLResponse)
    def ver_cuadrante(request: Request, cuadrante_id: int,
                      srv: ServicioCuadrantes = Depends(obtener_servicio)):
        cuad = srv.cuadrantes.cargar(cuadrante_id)
        if not cuad:
            return RedirectResponse("/", status_code=303)
        trabajadores = srv.mapa_trabajadores()
        cal = CalendarioMes(cuad.anio, cuad.mes)
        resumenes = calcular_resumenes(cuad, trabajadores, cal)
        informe = srv.auditar(cuad)

        filas = []
        for tid in cuad.trabajadores_ids:
            trab = trabajadores.get(tid)
            celdas = []
            for dia in cal.dias:
                a = cuad.obtener(tid, dia)
                clase = "libre"
                if a and a.es_trabajo:
                    clase = "noche" if a.es_noche else "dia"
                elif a and a.ausencia is TipoAusencia.VACACIONES:
                    clase = "vac"
                elif a and a.ausencia is TipoAusencia.BAJA_MEDICA:
                    clase = "baja"
                if cal.es_festivo_o_finde(dia) and clase == "libre":
                    clase = "finde"
                celdas.append({
                    "turno": a.codigo_turno() if a else "",
                    "puesto": a.codigo_puesto() if a else "",
                    "clase": clase,
                })
            r = resumenes.get(tid)
            filas.append({
                "nombre": trab.nombre if trab else str(tid),
                "celdas": celdas,
                "ht": r.horas_trabajadas if r else 0,
                "he": r.horas_extra if r else 0,
                "hn": r.horas_nocturnas if r else 0,
            })

        dias_cab = [{"n": d, "letra": cal.letra_dia(d), "finde": cal.es_festivo_o_finde(d)}
                    for d in cal.dias]
        return _ctx(request, "cuadrante.html",
             cuad=cuad, filas=filas, dias=dias_cab, informe=informe,
            resumenes=resumenes, trabajadores=trabajadores)

    @app.get("/cuadrante/{cuadrante_id}/{formato}")
    def descargar(cuadrante_id: int, formato: str,
                  srv: ServicioCuadrantes = Depends(obtener_servicio)):
        cuad = srv.cuadrantes.cargar(cuadrante_id)
        if not cuad:
            return RedirectResponse("/", status_code=303)
        nombre = f"Cuadrante_{NOMBRES_MES[cuad.mes]}_{cuad.anio}"
        tmp = Path("exportaciones")
        tmp.mkdir(exist_ok=True)
        if formato == "excel":
            ruta = srv.exportar_excel(cuad, tmp / f"{nombre}.xlsx")
            tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif formato == "pdf":
            ruta = srv.exportar_pdf(cuad, tmp / f"{nombre}.pdf")
            tipo = "application/pdf"
        elif formato == "informes":
            ruta = srv.exportar_informes(cuad, tmp / f"{nombre}_informes.pdf")
            tipo = "application/pdf"
        else:
            return RedirectResponse(f"/cuadrante/{cuadrante_id}", status_code=303)
        datos = ruta.read_bytes()
        return StreamingResponse(
            io.BytesIO(datos), media_type=tipo,
            headers={"Content-Disposition": f'attachment; filename="{ruta.name}"'})

    # ------------------------------------------------------------------
    @app.get("/equipo", response_class=HTMLResponse)
    def equipo(request: Request, srv: ServicioCuadrantes = Depends(obtener_servicio)):
        return _ctx(request, "equipo.html",
             trabajadores=srv.trabajadores.listar())

    @app.post("/equipo/nuevo")
    def equipo_nuevo(nombre: str = Form(...), puede_noches: str = Form("no"),
                     srv: ServicioCuadrantes = Depends(obtener_servicio)):
        if nombre.strip():
            srv.trabajadores.guardar(Trabajador(
                id=None, nombre=nombre.strip().upper(),
                puestos_diurnos_permitidos=set(Puesto),
                puestos_nocturnos_permitidos={Puesto.F1, Puesto.F2},
                puede_hacer_noches=(puede_noches == "si")))
        return RedirectResponse("/equipo", status_code=303)

    @app.post("/equipo/{trabajador_id}/baja")
    def equipo_baja(trabajador_id: int, srv: ServicioCuadrantes = Depends(obtener_servicio)):
        trab = srv.trabajadores.obtener(trabajador_id)
        if trab:
            trab.activo = not trab.activo
            srv.trabajadores.guardar(trab)
        return RedirectResponse("/equipo", status_code=303)

    @app.post("/equipo/sincronizar")
    def equipo_sincronizar(srv: ServicioCuadrantes = Depends(obtener_servicio)):
        sincronizar_equipo(srv)
        return RedirectResponse("/equipo", status_code=303)

    # ------------------------------------------------------------------
    @app.get("/ausencias", response_class=HTMLResponse)
    def ausencias(request: Request, srv: ServicioCuadrantes = Depends(obtener_servicio)):
        lista = srv.ausencias.listar_todas()
        nombres = {t.id: t.nombre for t in srv.trabajadores.listar()}
        tipos = [
            TipoAusencia.VACACIONES, TipoAusencia.BAJA_MEDICA,
            TipoAusencia.PERMISO_RETRIBUIDO, TipoAusencia.PERMISO_SIN_SUELDO,
            TipoAusencia.FORMACION, TipoAusencia.ASUNTOS_PROPIOS,
        ]
        return _ctx(request, "ausencias.html",
             ausencias=lista, nombres=nombres,
            trabajadores=srv.trabajadores.listar(solo_activos=True), tipos=tipos)

    @app.post("/ausencias/nueva")
    def ausencia_nueva(trabajador_id: int = Form(...), tipo: str = Form(...),
                       inicio: str = Form(...), fin: str = Form(...),
                       descripcion: str = Form(""),
                       srv: ServicioCuadrantes = Depends(obtener_servicio)):
        srv.ausencias.guardar(Ausencia(
            id=None, trabajador_id=trabajador_id, tipo=TipoAusencia(tipo),
            fecha_inicio=date.fromisoformat(inicio), fecha_fin=date.fromisoformat(fin),
            descripcion=descripcion))
        return RedirectResponse("/ausencias", status_code=303)

    @app.post("/ausencias/{ausencia_id}/eliminar")
    def ausencia_eliminar(ausencia_id: int, srv: ServicioCuadrantes = Depends(obtener_servicio)):
        srv.ausencias.eliminar(ausencia_id)
        return RedirectResponse("/ausencias", status_code=303)

    return app


# Instancia por defecto para «uvicorn cuadrantes.web.app:app».
app = crear_app()
