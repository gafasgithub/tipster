"""Agente Calendario: lee en Wikipedia los partidos y resultados de la Champions."""
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from .base import Agente

API_WIKIPEDIA = "https://en.wikipedia.org/w/api.php"
PAGINAS = [("league phase", "LEAGUE_STAGE"), ("knockout phase", None)]

CABECERA = re.compile(r"^(={2,5})\s*([^=\n]+?)\s*\1[ \t]*$", re.M)
ENLACE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
PAIS = re.compile(r"fbaicon\|(\w+)")
MARCADOR = re.compile(r"(\d+)\s*[–−-]\s*(\d+)")
FECHA = re.compile(r"Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})")
HORA = re.compile(r"(\d{1,2}):(\d{2})")
ETAPAS = [  # el orden importa: "semi-final" y "quarter-final" también contienen "final"
    ("play-off", "PLAYOFFS"), ("round of 16", "LAST_16"), ("quarter-final", "QUARTER_FINALS"),
    ("semi-final", "SEMI_FINALS"), ("final", "FINAL"),
]
NOMBRES_CORTOS = {
    "Paris Saint-Germain": "PSG", "Manchester City": "Man City", "Manchester United": "Man United",
    "Borussia Dortmund": "Dortmund", "Bayer Leverkusen": "Leverkusen", "Bayern Munich": "Bayern",
    "Atlético Madrid": "Atlético", "Inter Milan": "Inter", "Tottenham Hotspur": "Tottenham",
    "Newcastle United": "Newcastle", "Shakhtar Donetsk": "Shakhtar", "Eintracht Frankfurt": "Frankfurt",
    "Union Saint-Gilloise": "Union SG", "Olympique de Marseille": "Marseille", "Slovan Bratislava": "Slovan",
}


class AgenteCalendario(Agente):
    nombre = "calendario"

    def trabajar(self):
        temporada = temporada_actual(datetime.now(timezone.utc))
        partidos = []
        for sufijo, etapa in PAGINAS:
            pagina = f"{temporada} UEFA Champions League {sufijo}"
            texto = self._wikitexto(pagina)
            if texto is None:
                self.info(f"La página «{pagina}» aún no existe")
                continue
            nuevos = parsear(texto, etapa)
            self.info(f"«{pagina}»: {len(nuevos)} partidos leídos")
            partidos += nuevos
        if not partidos:
            raise RuntimeError(f"No se encontró ningún partido de la temporada {temporada} en Wikipedia")
        for n, p in enumerate(partidos):
            p["id"] = f"cl-{n}"

        jugados = [p for p in partidos if p["goles_local"] is not None]
        proximos = siguiente_jornada(partidos)
        if proximos:
            self.info(f"Próxima jornada: {len(proximos)} partidos desde el {proximos[0]['fecha'][:10]}")
        else:
            self.aviso("No hay partidos pendientes")
        self.metricas = {"partidos_temporada": len(partidos), "jugados": len(jugados), "proximos": len(proximos)}
        return {"temporada": temporada, "jugados": jugados, "proximos": proximos}

    def _wikitexto(self, pagina):
        parametros = urllib.parse.urlencode({
            "action": "parse", "page": pagina, "prop": "wikitext",
            "format": "json", "formatversion": 2, "redirects": 1,
        })
        datos = json.loads(self.descargar(f"{API_WIKIPEDIA}?{parametros}", horas_cache=1))
        return None if "error" in datos else datos["parse"]["wikitext"]


def temporada_actual(hoy):
    anio = hoy.year if hoy.month >= 7 else hoy.year - 1
    return f"{anio}–{(anio + 1) % 100:02d}"


def parsear(texto, etapa_por_defecto):
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    cabeceras = [(m.start(), len(m.group(1)), m.group(2)) for m in CABECERA.finditer(texto)]
    partidos = []
    for m in re.finditer(r"\{\{#invoke:Football box\|main", texto):
        fin = texto.find("\n}}", m.end())
        caja = texto[m.end():fin if fin != -1 else None]
        titulos = {}
        for posicion, nivel, titulo in cabeceras:
            if posicion > m.start():
                break
            titulos = {n: t for n, t in titulos.items() if n < nivel}
            titulos[nivel] = titulo
        partido = _partido(caja, [titulos[n] for n in sorted(titulos, reverse=True)], etapa_por_defecto)
        if partido:
            partidos.append(partido)
    return partidos


def _campo(caja, nombre):
    m = re.search(rf"^\|\s*{nombre}[ \t]*=[ \t]*(.*)$", caja, re.M)
    return m.group(1).strip() if m else ""


def _equipo(texto):
    texto = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", texto, flags=re.S)
    enlace = ENLACE.search(texto)
    if not enlace:
        return None  # equipo aún por decidir
    nombre = (enlace.group(2) or enlace.group(1)).strip()
    pais = PAIS.search(texto)
    palabras = re.split(r"[\s\-]+", nombre)
    return {
        "id": nombre, "nombre": nombre, "corto": NOMBRES_CORTOS.get(nombre, nombre),
        "tla": "".join(p[0] for p in palabras[:3]).upper() if len(palabras) > 1 else nombre[:3].upper(),
        "escudo": "", "pais": pais.group(1) if pais else "", "wiki": enlace.group(1).strip(),
    }


def _partido(caja, titulos, etapa_por_defecto):
    fecha = FECHA.search(_campo(caja, "date"))
    local, visitante = _equipo(_campo(caja, "team1")), _equipo(_campo(caja, "team2"))
    if not fecha or not local or not visitante:
        return None

    jornada, etapa = None, etapa_por_defecto
    for titulo in titulos:  # del más concreto al más general
        jornada_m = re.search(r"Matchday (\d+)", titulo)
        if jornada_m:
            jornada, etapa = int(jornada_m.group(1)), "LEAGUE_STAGE"
            break
        clave = next((e for texto, e in ETAPAS if texto in titulo.lower()), None)
        if clave:
            etapa = clave
            break

    hora = HORA.search(_campo(caja, "time"))
    hora_local = datetime(*map(int, fecha.groups()), *(map(int, hora.groups()) if hora else (21, 0)))
    utc = hora_local - timedelta(hours=_desfase_hora_central_europea(hora_local))
    marcador = MARCADOR.search(_campo(caja, "score"))
    arbitro = ENLACE.search(_campo(caja, "referee"))
    return {
        "fecha": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "estado": "FINISHED" if marcador else "TIMED",
        "etapa": etapa, "jornada": jornada, "competicion": "Champions",
        "local": local, "visitante": visitante,
        "goles_local": int(marcador.group(1)) if marcador else None,
        "goles_visitante": int(marcador.group(2)) if marcador else None,
        "arbitro": (arbitro.group(2) or arbitro.group(1)) if arbitro else None,
    }


def _ultimo_domingo(anio, mes):
    dia = datetime(anio, mes, 31)  # marzo y octubre tienen 31 días
    return dia - timedelta(days=(dia.weekday() + 1) % 7)


def _desfase_hora_central_europea(hora_local):
    """Wikipedia da las horas en CET (UTC+1) o, en verano, CEST (UTC+2)."""
    inicio = _ultimo_domingo(hora_local.year, 3).replace(hour=2)
    fin = _ultimo_domingo(hora_local.year, 10).replace(hour=3)
    return 2 if inicio <= hora_local < fin else 1


def _fecha_utc(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def siguiente_jornada(partidos):
    """Partidos sin resultado de la próxima jornada (incluye los que empezaron hace menos de 3 h)."""
    limite = datetime.now(timezone.utc) - timedelta(hours=3)
    pendientes = sorted(
        (p for p in partidos if p["goles_local"] is None and _fecha_utc(p["fecha"]) >= limite),
        key=lambda p: p["fecha"],
    )
    if not pendientes:
        return []
    primero = pendientes[0]
    if primero["jornada"] is not None:
        return [p for p in pendientes if (p["etapa"], p["jornada"]) == (primero["etapa"], primero["jornada"])]
    tope = _fecha_utc(primero["fecha"]) + timedelta(days=3)
    return [p for p in pendientes if _fecha_utc(p["fecha"]) <= tope]
