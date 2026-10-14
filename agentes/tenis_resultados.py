"""Agente Tenis-Resultados: descarga de tennis-data.co.uk los partidos ATP y WTA recientes."""
import io
import re
import urllib.parse
import zipfile
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree

from .base import Agente

URL_INDICE = "http://www.tennis-data.co.uk/alldata.php"
ANIOS_HISTORIAL = 2  # además del actual
XLSX = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ORDEN_RONDAS = {"1st Round": 1, "2nd Round": 2, "3rd Round": 3, "4th Round": 4,
                "Round Robin": 4, "Quarterfinals": 5, "Semifinals": 6, "The Final": 7}


class AgenteTenisResultados(Agente):
    nombre = "tenis-resultados"

    def trabajar(self):
        hoy = datetime.now(timezone.utc).date()
        indice = self.descargar(URL_INDICE, horas_cache=24).decode("latin-1")
        partidos = {"ATP": [], "WTA": []}
        for ruta, anio, femenino in re.findall(r'href="([^"]*/(\d{4})(w?)/\d{4}\.xlsx)"', indice, re.I):
            anio = int(anio)
            if anio < hoy.year - ANIOS_HISTORIAL:
                continue
            circuito = "WTA" if femenino else "ATP"
            contenido = self.descargar(urllib.parse.urljoin(URL_INDICE, ruta),
                                       horas_cache=12 if anio == hoy.year else 24 * 7)
            nuevos = [p for p in map(_partido, leer_xlsx(contenido)) if p]
            partidos[circuito] += nuevos
            self.info(f"{circuito} {anio}: {len(nuevos)} partidos")

        for circuito, lista in partidos.items():
            lista.sort(key=lambda p: (p["fecha"], ORDEN_RONDAS.get(p["ronda"], 0)))
            if lista:
                self.info(f"{circuito}: último resultado disponible del {lista[-1]['fecha']:%d/%m/%Y}")
        if not any(partidos.values()):
            raise RuntimeError("No se pudo leer ningún resultado de tennis-data.co.uk")
        self.metricas = {c: len(l) for c, l in partidos.items()}
        return partidos


def leer_xlsx(contenido):
    """Lee la primera hoja de un .xlsx sin librerías externas."""
    libro = zipfile.ZipFile(io.BytesIO(contenido))
    compartidos = []
    if "xl/sharedStrings.xml" in libro.namelist():
        raiz = ElementTree.fromstring(libro.read("xl/sharedStrings.xml"))
        compartidos = ["".join(si.itertext()) for si in raiz.findall("m:si", XLSX)]
    hoja = ElementTree.fromstring(libro.read("xl/worksheets/sheet1.xml"))
    filas = []
    for fila in hoja.find("m:sheetData", XLSX):
        valores = {}
        for celda in fila:
            v = celda.find("m:v", XLSX)
            if v is None:
                continue
            valor = compartidos[int(v.text)] if celda.get("t") == "s" else v.text
            valores[re.match(r"[A-Z]+", celda.get("r")).group()] = valor
        filas.append(valores)
    if not filas:
        return []
    cabecera = filas[0]
    return [{cabecera[c]: v for c, v in f.items() if c in cabecera} for f in filas[1:]]


def _entero(valor):
    try:
        return int(float(str(valor).strip()))
    except (TypeError, ValueError):
        return None


def _partido(f):
    if (f.get("Comment") or "Completed").strip() != "Completed":
        return None  # se descartan abandonos y walkovers
    ganador, perdedor = (f.get("Winner") or "").strip(), (f.get("Loser") or "").strip()
    serie = _entero(f.get("Date"))
    if not ganador or not perdedor or serie is None:
        return None
    sets = []
    for n in range(1, 6):
        juegos_g, juegos_p = _entero(f.get(f"W{n}")), _entero(f.get(f"L{n}"))
        if juegos_g is None or juegos_p is None:
            break
        sets.append((juegos_g, juegos_p))
    if not sets:
        return None
    superficie = (f.get("Surface") or "Hard").strip()
    return {
        "fecha": date(1899, 12, 30) + timedelta(days=serie),
        "torneo": (f.get("Tournament") or "").strip(),
        "superficie": "Hard" if superficie == "Carpet" else superficie,
        "ronda": (f.get("Round") or "").strip(),
        "ganador": ganador, "perdedor": perdedor,
        "ranking_ganador": _entero(f.get("WRank")), "ranking_perdedor": _entero(f.get("LRank")),
        "sets": sets,
    }
