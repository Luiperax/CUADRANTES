#!/usr/bin/env python3
"""
Importa al historial los cuadrantes REALES de enero a agosto de 2026.

Ejecútelo UNA vez en el portátil, en la carpeta del programa:

    python importar_historico_2026.py

Toma los cuadrantes definitivos de cada mes (extraídos del libro de cálculo
oficial y verificados contra los totales H.T./H.N. de cada persona) y los añade
al historial. Solo se importan los trabajadores del EQUIPO ACTUAL (los que
siguen en el centro); los que ya no están no hacen falta para el reparto futuro.

Así, al generar los próximos meses, el reparto de festivos, noches, fines de
semana, horas y puestos tendrá en cuenta TODO lo trabajado en el año.

Este script SUSTITUYE a importar_agosto_2026.py (ya incluye agosto).
Es idempotente: si se ejecuta dos veces no duplica nada, reemplaza cada mes.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date

from cuadrantes.config.constantes import EstadoCuadrante, Puesto, TipoAusencia, Turno
from cuadrantes.datos.datos_iniciales import EQUIPO_ACTUAL, cargar_plantilla_ejemplo
from cuadrantes.datos.modelos import Asignacion, Cuadrante, Trabajador
from cuadrantes.dominio.computos import calcular_resumenes
from cuadrantes.rutas import ruta_base_datos
from cuadrantes.servicio import ServicioCuadrantes

# Datos por mes: { "mes": { "NOMBRE": "tok tok ... (un token por día)" } }
# Token: "MT/F1", "TN/F2"...  |  "V" = vacaciones  |  "." = libre/descanso/ausencia.
MESES = json.loads(r"""{
"1": {
"FERNANDO CEMBRERO ANTOLÍN": ". MT/F1 MT/F1 MT/F1 MT/F1 . MT/MO MT/F1 MT/F1 . . MT/EX MT/F2 MT/MO . . . . MT/F1 MT/F1 MT/F1 . MT/MO . . MT/F1 MT/F1 MT/F1 MT/F2 . .",
"SANTIAGO R. MANRIQUE GÓMEZ": "MT/F2 MT/EX . . MT/MO . . MT/EX . . . MT/F2 MT/EX MT/EX MT/F2 MT/MO . . . MT/EX MT/F2 . . MT/F2 MT/F2 MT/F2 MT/EX MT/F2 . TN/F2 TN/F1",
"DANIEL LABERNIA GONZÁLEZ": "MT/F1 MT/F2 . . . . TN/F2 TN/F1 TN/F1 . . . . . MT/MO TN/F1 TN/F2 TN/F1 . . TN/F1 TN/F2 . . . . . MT/MO . MT/EX MT/F1",
"JAVIER CALDERON FERNÁNDEZ": ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
"Mª VICTORIA CANO MARTINEZ": "TN/F2 TN/F1 . . . . V V V V V V V V . TN/F2 TN/F1 TN/F2 . . MT/MO MT/EX MT/F2 . . TN/F1 TN/F2 TN/F1 . . MT/F2",
"JAVIER PEREZ GALLARDO": ". MT/MO MT/F2 MT/F2 . . TN/F1 TN/F2 . MT/F2 MT/F1 . MT/MO TN/F1 TN/F2 . . . MT/F2 MT/MO . MT/MO TN/F1 TN/F2 TN/F1 . . . MT/EX MT/MO .",
"LUIS PERALTA ROS": ". . . . MT/EX MT/F1 MT/F2 . MT/MO MT/F1 MT/F2 MT/MO . MT/F2 MT/EX MT/F2 . . . TN/F1 TN/F2 TN/F1 . . . MT/EX MT/F2 MT/EX TN/F2 TN/F1 TN/F2",
"ALICIA GUTIERREZ SANCHEZ": "TN/F1 . TN/F2 TN/F1 TN/F2 TN/F1 . . TN/F2 TN/F1 TN/F2 . . TN/F2 TN/F1 . MT/F1 MT/F2 TN/F2 . . . . . . . . . TN/F1 . ."
},
"2": {
"FERNANDO CEMBRERO ANTOLÍN": ". MT/F1 MT/F1 MT/F1 MT/EX MT/MO . MT/F2 MT/F1 MT/F1 MT/F1 . . . . MT/F1 MT/F1 . . . MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 . . .",
"SANTIAGO R. MANRIQUE GÓMEZ": ". . MT/EX MT/F2 MT/MO MT/EX . . MT/EX MT/EX . MT/F2 . . . . MT/MO MT/F2 MT/F2 MT/EX . . MT/EX TN/F1 TN/F2 . . MT/F2",
"DANIEL LABERNIA GONZÁLEZ": "MT/F2 MT/EX MT/MO . . . . . . . . . MT/F2 MT/F2 MT/F2 TN/F2 TN/F1 TN/F2 TN/F1 . . . TN/F1 TN/F2 TN/F1 TN/F2 . .",
"JAVIER CALDERON FERNÁNDEZ": ". . . . . . . . . . . . . . . . . . . . . . . . . . . .",
"Mª VICTORIA CANO MARTINEZ": "MT/F1 MT/F2 . TN/F1 TN/F2 . . . . . TN/F2 TN/F2 TN/F1 TN/F2 TN/F1 . . MT/EX MT/MO MT/MO . . . . . TN/F1 TN/F1 TN/F2",
"JAVIER PEREZ GALLARDO": "TN/F2 TN/F1 TN/F2 . MT/F2 MT/F2 . . MT/MO MT/F2 . . . . . MT/EX MT/F2 MT/MO . TN/F1 TN/F2 TN/F1 TN/F2 . . MT/F2 MT/MO .",
"LUIS PERALTA ROS": "TN/F1 . MT/F2 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . TN/F2 TN/F1 TN/F1 TN/F2 TN/F1 TN/F2 . . . . . . . . . . . TN/F2 TN/F1"
},
"3": {
"FERNANDO CEMBRERO ANTOLÍN": ". MT/F1 MT/F1 MT/F1 . MT/F1 . . MT/F1 MT/F1 MT/F1 . MT/F1 MT/F1 MT/F1 MT/F1 . MT/F1 MT/F1 MT/F1 . . MT/F1 MT/F1 MT/F1 V V V V V V",
"SANTIAGO R. MANRIQUE GÓMEZ": "MT/F1 MT/MO MT/EX . MT/EX MT/EX MT/F1 MT/F2 MT/EX . . . . . . MT/F2 MT/F2 MT/MO MT/F2 MT/F2 MT/F2 MT/F2 MT/F2 MT/MO MT/F2 MT/F2 . . . V V",
"DANIEL LABERNIA GONZÁLEZ": ". . TN/F1 TN/F2 . . . . . TN/F1 TN/F2 TN/F1 TN/F2 . . MT/EX MT/EX MT/F2 . MT/EX . . . . MT/EX TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 TN/F1",
"JAVIER CALDERON FERNÁNDEZ": ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
"Mª VICTORIA CANO MARTINEZ": "TN/F1 TN/F2 . . TN/F2 TN/F1 . . . TN/F2 TN/F1 TN/F2 . TN/F1 TN/F2 TN/F2 TN/F1 TN/F2 . . . V V V TN/F2 TN/F1 . MT/F2 MT/F1 . .",
"JAVIER PEREZ GALLARDO": ". MT/EX TN/F2 TN/F1 . . MT/F2 MT/F1 MT/F2 MT/F2 MT/EX MT/F2 MT/F2 MT/F2 MT/F2 . MT/MO . . . . . MT/MO MT/EX . MT/MO TN/F2 TN/F1 TN/F2 TN/F1 TN/F2",
"LUIS PERALTA ROS": "TN/F2 TN/F1 . MT/F2 MT/F1 V V V V MT/EX MT/F2 MT/F1 MT/EX . . . MT/F1 MT/EX MT/EX TN/F1 TN/F2 TN/F1 . V V MT/F1 MT/F1 . . MT/F1 MT/F1",
"ALICIA GUTIERREZ SANCHEZ": ". . . . . . . . . . . . MT/MO . . . . . . . . . . . . . . . . . .",
"MOHAMED AMAR MOHAMED": ". . . MT/MO MT/MO MT/MO . . MT/MO MT/MO MT/MO MT/MO . . . . . . . MT/MO MT/F1 MT/F1 TN/F2 TN/F2 TN/F1 . MT/MO MT/F1 MT/F2 MT/MO MT/MO"
},
"4": {
"FERNANDO CEMBRERO ANTOLÍN": "V . . . . . . MT/F1 MT/F1 . MT/F1 MT/F1 MT/F1 . MT/F1 MT/F1 MT/F1 . . . MT/EX MT/F2 MT/F1 MT/EX MT/F1 . MT/F1 MT/F1 MT/F2 MT/F1",
"SANTIAGO R. MANRIQUE GÓMEZ": "V V V V V . . . MT/EX MT/MO . . MT/EX MT/F2 MT/EX MT/EX MT/MO . . MT/F2 MT/F2 MT/EX . . . . MT/EX MT/EX . MT/MO",
"DANIEL LABERNIA GONZÁLEZ": ". . . . . V V V V V V V V . . TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . . . . . TN/F2 TN/F2 TN/F1",
"JAVIER CALDERON FERNÁNDEZ": ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
"Mª VICTORIA CANO MARTINEZ": "MT/EX MT/F2 MT/F1 MT/F2 MT/F1 TN/F2 TN/F1 . . TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 . . . . . . . V V V V V V V V",
"JAVIER PEREZ GALLARDO": "TN/F2 . . . . MT/F2 MT/EX MT/EX MT/MO . . . . . MT/MO TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . . . MT/F2 . MT/MO MT/F2",
"LUIS PERALTA ROS": "MT/F1 . . . . MT/F1 MT/F1 MT/F2 MT/F2 MT/F1 . . . MT/F1 . MT/MO MT/EX . . MT/F1 MT/F1 MT/F1 MT/EX MT/F1 . MT/F1 . MT/MO MT/F1 MT/EX",
"ALICIA GUTIERREZ SANCHEZ": ". MT/F1 MT/F2 MT/F1 MT/F2 . . . . . . . . . . . . . . . . . . . . . TN/F2 TN/F1 . .",
"MOHAMED AMAR MOHAMED": "MT/MO . . . . MT/MO MT/MO MT/MO TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . . . . MT/MO MT/MO MT/MO MT/MO TN/F2 TN/F1 TN/F2 TN/F1 . TN/F1 TN/F2",
"EUGENIA DEL PILAR VILEMA VILEMA": ". . . . . . . . . MT/EX . . MT/MO MT/EX . . . MT/F2 MT/F1 . . . . . . . . . . ."
},
"5": {
"FERNANDO CEMBRERO ANTOLÍN": ". . . MT/F1 MT/F1 MT/EX MT/F1 MT/MO . . MT/EX . MT/EX MT/F1 MT/F1 MT/F2 MT/F1 . . . MT/F2 MT/F1 . . MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 . .",
"SANTIAGO R. MANRIQUE GÓMEZ": ". . . MT/F2 . . MT/MO MT/F2 MT/F2 MT/F2 MT/F2 MT/EX . . . . . MT/F2 MT/F2 MT/EX MT/EX . MT/F2 MT/F2 MT/EX MT/MO MT/F2 MT/F2 . MT/F1 MT/F2",
"DANIEL LABERNIA GONZÁLEZ": "TN/F1 TN/F2 TN/F1 . . . MT/EX . . . . MT/MO MT/MO MT/EX . . . . . TN/F1 TN/F1 . TN/F2 TN/F1 . . . MT/EX MT/F2 TN/F2 TN/F1",
"JAVIER CALDERON FERNÁNDEZ": ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
"Mª VICTORIA CANO MARTINEZ": "TN/F2 TN/F1 TN/F2 . TN/F1 TN/F2 TN/F2 . . . TN/F1 TN/F2 TN/F1 TN/F1 . . . . . . . TN/F2 TN/F1 TN/F2 . . TN/F2 TN/F2 TN/F2 TN/F1 TN/F2",
"JAVIER PEREZ GALLARDO": ". . . TN/F2 TN/F2 TN/F1 . TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 . . MT/F2 MT/F1 MT/F2 MT/MO TN/F1 . . . . V V V V V V V V",
"LUIS PERALTA ROS": "MT/F1 MT/F2 MT/F1 . MT/EX MT/F1 . MT/F1 . . MT/F1 MT/F1 MT/F1 MT/F2 . . . MT/F1 MT/F1 MT/F1 MT/F1 MT/F2 . . V V V V V V V",
"ALICIA GUTIERREZ SANCHEZ": "MT/F2 MT/F1 MT/F2 . . . . . . . . . . . . . . . . . . . . . . MT/F2 . . . . .",
"MOHAMED AMAR MOHAMED": ". . . MT/MO MT/MO . TN/F1 TN/F2 TN/F1 TN/F2 . . TN/F2 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . MT/MO MT/MO MT/MO . . TN/F1 TN/F2 . MT/MO MT/MO . .",
"EUGENIA DEL PILAR VILEMA VILEMA": ". . . TN/F1 . MT/MO . . MT/F1 MT/F1 MT/MO MT/F2 . . TN/F2 TN/F1 TN/F2 . MT/MO . . MT/EX MT/F1 MT/F1 MT/MO . MT/MO . . . .",
"IVÁN DÍAZ MOYA": ". . . . . . . . . . . . . . . . . . . . . . . . . . . . MT/EX MT/F2 MT/F1"
},
"6": {
"FERNANDO CEMBRERO ANTOLÍN": "MT/F1 MT/F1 MT/F1 MT/F1 . . . MT/F2 MT/EX MT/F1 . MT/F1 . . MT/F1 MT/MO MT/F1 . . MT/F1 MT/F1 MT/F1 . MT/F2 MT/F2 MT/F1 . . MT/F1 MT/F1",
"SANTIAGO R. MANRIQUE GÓMEZ": "MT/MO MT/MO MT/MO MT/F2 MT/EX . . MT/MO MT/F2 MT/EX MT/EX . MT/F2 MT/F2 MT/F2 MT/EX MT/EX MT/F2 MT/EX . . MT/EX . . . . . . MT/EX MT/F2",
"DANIEL LABERNIA GONZÁLEZ": ". . TN/F2 TN/F2 . . . TN/F2 TN/F1 TN/F2 . TN/F2 TN/F2 TN/F1 TN/F1 TN/F2 . . . . . MT/F2 MT/MO TN/F2 . TN/F1 TN/F2 TN/F1 . .",
"JAVIER CALDERON FERNÁNDEZ": ". . . . . . . . . . . . . . V V V V V V V V V V V V V V V V",
"Mª VICTORIA CANO MARTINEZ": "TN/F1 TN/F2 TN/F1 . TN/F1 TN/F2 TN/F1 TN/F1 . . TN/F2 TN/F1 TN/F1 TN/F2 TN/F2 . . MT/MO . . . . V V V V V V V V",
"JAVIER PEREZ GALLARDO": "MT/EX MT/EX . TN/F1 TN/F2 TN/F1 TN/F2 . TN/F2 TN/F1 TN/F1 . . . . . TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F1 . . MT/EX MT/MO MT/F2 MT/F1 . MT/MO",
"LUIS PERALTA ROS": "V . MT/EX MT/EX MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 . MT/F1 MT/EX MT/F1 MT/F1 MT/EX MT/F1 . MT/F1 MT/F1 . . . MT/F1 MT/F1 MT/F1 . . . . MT/EX",
"ALICIA GUTIERREZ SANCHEZ": ". . . . . . MT/F2 . . . . . . . . . . . . . . . . . TN/F1 . . . . .",
"MOHAMED AMAR MOHAMED": "TN/F2 TN/F1 . MT/MO MT/MO . . . MT/MO MT/MO . MT/MO . . MT/MO TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 TN/F2 TN/F2 TN/F1 TN/F2 . TN/F1 TN/F2 TN/F2 TN/F1",
"EUGENIA DEL PILAR VILEMA VILEMA": ". . . . . . . . . . . . . . . . MT/F2 . . MT/F2 MT/F2 MT/MO MT/EX MT/MO . MT/F2 MT/F1 MT/F2 MT/MO .",
"IVÁN DÍAZ MOYA": ". MT/F2 MT/F2 . MT/F2 MT/F2 . MT/EX . . MT/F2 MT/F2 . . . MT/F2 MT/MO MT/EX MT/MO . . . MT/F2 MT/EX MT/MO MT/EX . . MT/F2 ."
},
"7": {
"FERNANDO CEMBRERO ANTOLÍN": "MT/EX . . . . . MT/F2 MT/F1 MT/F1 MT/F1 . . MT/F1 MT/F2 MT/F1 . MT/MO MT/F1 MT/F1 MT/EX MT/F2 MT/MO . MT/F1 MT/F2 . MT/F1 MT/F1 MT/F1 MT/F1 MT/F1",
"SANTIAGO R. MANRIQUE GÓMEZ": ". MT/MO MT/EX . . MT/MO . MT/F2 MT/EX MT/F2 MT/F1 MT/F2 . . MT/F2 MT/MO . . . MT/F2 . . . MT/EX MT/F1 MT/F2 MT/EX MT/F2 MT/F2 MT/EX MT/EX",
"DANIEL LABERNIA GONZÁLEZ": ". . . . . . . . . . . . . . . . . . . . . . MT/F2 TN/F1 . . TN/F1 . TN/F1 . .",
"JAVIER CALDERON FERNÁNDEZ": "MT/F2 MT/F2 . . . . . MT/EX . . MT/F2 MT/F1 MT/MO MT/EX MT/MO MT/F2 MT/EX . . MT/MO MT/EX MT/F2 MT/MO MT/MO TN/F2 TN/F1 TN/F2 TN/F2 . MT/F2 MT/MO",
"Mª VICTORIA CANO MARTINEZ": ". . . . . . TN/F1 TN/F2 TN/F1 . TN/F1 TN/F2 TN/F1 TN/F1 . MT/EX MT/F2 TN/F2 TN/F1 TN/F2 TN/F1 TN/F1 TN/F1 . TN/F1 TN/F2 . TN/F1 . TN/F2 TN/F1",
"JAVIER PEREZ GALLARDO": "TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . MT/MO MT/F2 MT/EX . . MT/F2 MT/MO . . V V V V V V V V V V V V V V V",
"LUIS PERALTA ROS": "MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 . . . . . MT/EX MT/F1 MT/EX MT/F1 MT/F1 MT/F2 MT/F2 MT/F1 MT/F1 MT/F1 MT/F1 MT/F2 . . V V V V V",
"MOHAMED AMAR MOHAMED": "TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . MT/MO MT/MO . . V V V V V V V TN/F1 TN/F2 TN/F2 TN/F2 TN/F2 . . MT/MO MT/MO MT/MO MT/MO TN/F2",
"EUGENIA DEL PILAR VILEMA VILEMA": ". . MT/MO MT/F2 MT/F2 MT/F2 MT/MO . . . . . . TN/F2 TN/F2 TN/F1 TN/F2 TN/F1 TN/F2 . MT/MO MT/EX MT/EX . . MT/F1 MT/F2 MT/EX MT/EX . MT/F2",
"IVÁN DÍAZ MOYA": "MT/MO MT/EX MT/F2 . . MT/EX MT/EX TN/F1 TN/F2 TN/F2 TN/F2 TN/F1 . . . V V V V V V V V V V V V V V V V"
},
"8": {
"FERNANDO CEMBRERO ANTOLÍN": ". . MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 . . MT/F1 MT/F1 MT/EX MT/F2 MT/EX . . MT/F1 MT/F1 MT/F1 MT/EX . . . V V V V V V V V",
"SANTIAGO R. MANRIQUE GÓMEZ": "V V V V V V V V V V V V V V V V . . MT/F2 MT/MO MT/EX . . MT/EX MT/EX MT/MO MT/F2 MT/MO MT/F2 MT/F2 .",
"DANIEL LABERNIA GONZÁLEZ": ". . . . . MT/EX TN/F1 TN/F2 TN/F1 TN/F1 TN/F2 TN/F1 . . . . TN/F2 TN/F2 . . . MT/F2 MT/F1 MT/F2 . MT/EX . MT/F2 . . .",
"JAVIER CALDERON FERNÁNDEZ": ". . MT/F2 MT/EX MT/EX . MT/F2 MT/F2 MT/F1 . MT/EX MT/F2 MT/EX MT/MO . . MT/F2 MT/EX MT/MO . MT/F2 . . . MT/F2 MT/F2 MT/MO MT/EX . . MT/F2",
"Mª VICTORIA CANO MARTINEZ": ". . V V V V V V V MT/F2 TN/F1 TN/F2 TN/F2 TN/F2 TN/F2 TN/F1 . . . . TN/F2 TN/F2 TN/F1 TN/F2 TN/F2 TN/F1 TN/F1 . . . MT/EX",
"JAVIER PEREZ GALLARDO": ". . . TN/F1 TN/F1 TN/F2 . . . . . MT/MO TN/F1 TN/F1 TN/F1 TN/F2 TN/F1 . TN/F1 TN/F2 . . . MT/MO MT/MO . MT/EX TN/F1 TN/F2 TN/F1 TN/F1",
"LUIS PERALTA ROS": "V V V V V V V V V V V MT/F1 MT/F1 MT/F1 . . . . . MT/F1 MT/F1 . . MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 MT/F1 MT/F1",
"ALICIA GUTIERREZ SANCHEZ": "MT/F1 MT/F2 MT/MO MT/F2 . TN/F1 TN/F2 TN/F1 TN/F2 TN/F2 . . MT/MO . MT/F1 MT/F2 MT/EX . . . . . . . TN/F1 TN/F2 TN/F2 TN/F2 TN/F1 TN/F2 TN/F2",
"MOHAMED AMAR MOHAMED": "TN/F1 TN/F2 TN/F1 . MT/MO MT/MO MT/MO . . V V V V V V V . MT/MO TN/F1 TN/F2 TN/F1 TN/F1 TN/F2 TN/F1 . . MT/MO . . . MT/MO",
"EUGENIA DEL PILAR VILEMA VILEMA": "TN/F2 TN/F1 TN/F2 TN/F2 TN/F2 . MT/EX MT/F1 MT/F2 MT/EX MT/MO . . . . . MT/MO TN/F1 . . MT/MO V V V V V V V V V V",
"IVÁN DÍAZ MOYA": "MT/F2 MT/F1 MT/EX MT/MO MT/F2 MT/F2 . . . MT/MO MT/F2 . . MT/F2 MT/F2 MT/F1 . MT/F2 MT/EX MT/F2 . MT/F1 MT/F2 . . . . . . . ."
}
}""")

DIAS_MES = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31}
NOMBRE_MES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo",
              6: "junio", 7: "julio", 8: "agosto"}


def _norm(nombre: str) -> str:
    """Nombre en mayúsculas y sin tildes (ª -> A) para emparejar sin duplicar."""
    s = "".join(c for c in unicodedata.normalize("NFD", nombre)
                if unicodedata.category(c) != "Mn")
    return " ".join(s.upper().replace("\u00aa", "A").split())


def _parsear(token: str):
    if token == ".":
        return None, None, TipoAusencia.LIBRE
    if token == "V":
        return None, None, TipoAusencia.VACACIONES
    turno_txt, puesto_txt = token.split("/")
    return Turno(turno_txt), Puesto(puesto_txt), None


def main() -> int:
    servicio = ServicioCuadrantes(str(ruta_base_datos()))
    cargar_plantilla_ejemplo(servicio)

    # Índice de trabajadores existentes por nombre normalizado (crea los que falten).
    por_norma = {_norm(t.nombre): t for t in servicio.trabajadores.listar()}
    todos_puestos = set(Puesto)
    # Personal FIJO = el equipo actual del centro. Quien aparezca en el histórico
    # sin ser fijo (p. ej. Alicia, de refuerzo) se marca como NO activo: se conserva
    # su historial pero el programa no la mete sola en los próximos cuadrantes.
    fijos_norma = {_norm(e.nombre) for e in EQUIPO_ACTUAL}
    nombres_datos = {n for mm in MESES.values() for n in mm}
    for nombre in sorted(nombres_datos):
        es_fijo = _norm(nombre) in fijos_norma
        existente = por_norma.get(_norm(nombre))
        if existente is None:
            existente = servicio.trabajadores.guardar(Trabajador(
                id=None, nombre=nombre, activo=es_fijo,
                puestos_diurnos_permitidos=set(todos_puestos),
                puestos_nocturnos_permitidos={Puesto.F1, Puesto.F2},
                notas="Personal de refuerzo (histórico 2026)." if not es_fijo
                      else "Añadido al importar el histórico 2026."))
            por_norma[_norm(nombre)] = existente
        elif not es_fijo and existente.activo:
            # Ya existía como activo pero no es fijo: pasarlo a eventual.
            existente.activo = False
            servicio.trabajadores.guardar(existente)

    trab = {t.id: t for t in servicio.trabajadores.listar()}
    total_ok = 0
    for mes_str in sorted(MESES, key=int):
        mes = int(mes_str)
        datos_mes = MESES[mes_str]
        nd = DIAS_MES[mes]
        ids = []
        cuad = Cuadrante(
            id=None, anio=2026, mes=mes, empresa="NATURGY", sede="AV. SAN LUIS - 77",
            computo_mensual=162.0, estado=EstadoCuadrante.VALIDADO,
            fecha_generacion=date.today(), trabajadores_ids=[])
        for nombre, cadena in datos_mes.items():
            t = por_norma[_norm(nombre)]
            ids.append(t.id)
            celdas = cadena.split()
            if len(celdas) != nd:
                print(f"  AVISO {NOMBRE_MES[mes]}: {nombre} tiene {len(celdas)} días (esperado {nd})")
            for i, token in enumerate(celdas):
                turno, puesto, ausencia = _parsear(token)
                cuad.establecer(Asignacion(t.id, i + 1, turno=turno, puesto=puesto, ausencia=ausencia))
        cuad.trabajadores_ids = ids

        # Reemplazar si ya existía ese mes (idempotente).
        existente = servicio.cuadrantes.ultima_version(2026, mes)
        if existente is not None:
            cuad.id = existente.id
            cuad.version = existente.version

        servicio.cuadrantes.guardar(cuad)

        resu = calcular_resumenes(cuad, trab)
        tt = sum(r.dias_trabajados for r in resu.values())
        nn = sum(r.numero_noches for r in resu.values())
        print(f"  {NOMBRE_MES[mes].capitalize():10} — {len(ids):2d} trabajadores, "
              f"{tt:3d} turnos, {nn:3d} noches  [guardado]")
        total_ok += 1

    print(f"\n\u2705 {total_ok} meses (enero-agosto 2026) añadidos al historial.")
    print("   Ábralos en el programa para revisarlos. A partir de ahora el reparto")
    print("   tendrá en cuenta todo el año.")
    servicio.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
