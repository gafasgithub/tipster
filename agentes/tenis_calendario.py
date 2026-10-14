"""Agente Tenis-Calendario: busca en Wikipedia los torneos en juego y sus partidos pendientes."""
import re
from datetime import date, datetime, timedelta, timezone

from .base import Agente

MESES = {m: n for n, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
FECHA_SEMANA = re.compile(r"\b(\d{1,2})\s+([A-Z][a-z]{2})[a-z]*\b|\b([A-Z][a-z]{2})[a-z]*\s+(\d{1,2})\b")
ENLACE_TORNEO = re.compile(r"\[\[(\d{4} [^\]|]+)\|([^\]]+)\]\]")
ENLACE_CUADRO = re.compile(r"\[\[(\d{4} [^\]|]*– (?:Singles|Men's singles|Women's singles))\|")
ENLACE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
PAIS = re.compile(r"flagicon\|(\w+)")
SUPERFICIE = re.compile(r"(Hard|Clay|Grass|Carpet)\s*(\(i\))?")
RONDAS = {
    "first round": "1.ª ronda", "second round": "2.ª ronda", "third round": "3.ª ronda",
    "fourth round": "4.ª ronda", "round of 16": "Octavos", "quarterfinals": "Cuartos de final",
    "semifinals": "Semifinales", "final": "Final",
}


class AgenteTenisCalendario(Agente):
    nombre = "tenis-calendario"

    def trabajar(self):
        hoy = datetime.now(timezone.utc).date()
        torneos = []
        for circuito in ("ATP", "WTA"):
            pagina = f"{hoy.year} {circuito} Tour"
            texto = self.wikitexto(pagina, horas_cache=3)
            if texto is None:
                self.aviso(f"No existe la página «{pagina}»")
                continue
            en_juego = [t for t in torneos_del_calendario(texto, hoy.year, circuito)
                        if t["inicio"] - timedelta(days=3) <= hoy <= t["fin"]]
            self.info(f"{circuito}: {len(en_juego)} torneos esta semana "
                      f"({', '.join(t['nombre'] for t in en_juego) or 'ninguno'})")
            torneos += en_juego

        partidos = []
        for torneo in torneos:
            if not torneo["cuadro"]:
                self.aviso(f"{torneo['nombre']}: Wikipedia aún no tiene la página del cuadro")
                continue
            texto = self.wikitexto(torneo["cuadro"])
            if texto is None:
                self.aviso(f"{torneo['nombre']}: no existe «{torneo['cuadro']}»")
                continue
            nuevos = partidos_pendientes(texto, torneo)
            self.info(f"{torneo['nombre']} ({torneo['circuito']}, {torneo['superficie']}): "
                      f"{len(nuevos)} partidos pendientes")
            partidos += nuevos

        if not partidos:
            self.aviso("No hay partidos de tenis pendientes con los dos jugadores ya decididos")
        self.metricas = {"torneos": len(torneos), "partidos": len(partidos)}
        return {"torneos": [{k: v for k, v in t.items() if k not in ("inicio", "fin")} for t in torneos],
                "partidos": partidos}


def _fechas(texto, anio):
    fechas = []
    for m in FECHA_SEMANA.finditer(texto):
        dia, mes = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if mes.lower() in MESES:
            fechas.append(date(anio, MESES[mes.lower()], int(dia)))
    return fechas


def _limpiar(texto):
    texto = ENLACE.sub(lambda m: m.group(2) or m.group(1), texto)
    return re.sub(r"\{\{[^}]*\}\}|'''|''", "", texto).strip()


def torneos_del_calendario(texto, anio, circuito):
    torneos, semana = [], None
    for fila in re.split(r"\n\|-", texto):
        enlace = ENLACE_TORNEO.search(fila)
        fechas = _fechas(fila[:enlace.start()] if enlace else fila, anio)
        if fechas:
            semana = fechas
        if not enlace or not semana or not re.match(r"\s*<br", fila[enlace.end():]):
            continue
        celda = fila[enlace.start():].split("||")[0]
        partes = re.split(r"<br\s*/?>", celda)
        if len(partes) < 4:
            continue
        superficie = SUPERFICIE.search(partes[3])
        if not superficie:
            continue
        categoria = _limpiar(partes[2])
        cuadro = ENLACE_CUADRO.search(celda)
        torneos.append({
            "nombre": _limpiar(enlace.group(2)), "ciudad": _limpiar(partes[1]),
            "circuito": circuito, "categoria": categoria,
            "superficie": "Hard" if superficie.group(1) == "Carpet" else superficie.group(1),
            "interior": bool(superficie.group(2)),
            "mejor_de": 5 if circuito == "ATP" and "Grand Slam" in categoria else 3,
            "inicio": semana[0], "fin": semana[-1] + timedelta(days=6),
            "cuadro": cuadro.group(1) if cuadro else None,
        })
    return torneos


def _plantillas_cuadro(texto):
    for m in re.finditer(r"\{\{\s*[\w-]*Bracket[\w-]*", texto):
        nivel, i = 0, m.start()
        while i < len(texto):
            if texto.startswith("{{", i):
                nivel, i = nivel + 1, i + 2
            elif texto.startswith("}}", i):
                nivel, i = nivel - 1, i + 2
                if nivel == 0:
                    break
            else:
                i += 1
        yield texto[m.start():i]


def _jugador(valor):
    enlace = ENLACE.search(valor.replace("'''", ""))
    if not enlace:
        return None
    pais = PAIS.search(valor)
    nombre = re.sub(r"\s*\([^)]*\)", "", enlace.group(1)).strip()
    alias = (enlace.group(2) or "").strip()
    return {"nombre": nombre, "pais": pais.group(1) if pais else "", "alias": alias if alias != nombre else ""}


def _partidos_del_cuadro(texto):
    """Recorre todas las plantillas de cuadro (sin la fase previa) y devuelve, por cada partido
    con los dos jugadores conocidos: (nombre de la ronda, casilla A, casilla B). Cada casilla
    trae el jugador, si está en negrita (= ganador) y las puntuaciones de cada set."""
    corte = re.search(r"^==+\s*Qualif", texto, re.M)
    texto = re.sub(r"<!--.*?-->", "", texto[:corte.start()] if corte else texto, flags=re.S)
    for bloque in _plantillas_cuadro(texto):
        rondas, casillas = {}, {}
        for linea in bloque.splitlines():
            m = re.match(r"\s*\|\s*(RD\d+(?:-[a-z]+\d+(?:-\d+)?)?)\s*=\s*(.*)$", linea)
            if not m:
                continue
            clave, valor = m.group(1), m.group(2).strip()
            if r := re.fullmatch(r"RD(\d+)", clave):
                rondas[int(r.group(1))] = _limpiar(valor)
            elif r := re.fullmatch(r"RD(\d+)-team(\d+)", clave):
                casilla = casillas.setdefault((int(r.group(1)), int(r.group(2))), {"puntuaciones": {}})
                casilla["jugador"] = _jugador(valor)
                casilla["gana"] = "'''" in valor
            elif r := re.fullmatch(r"RD(\d+)-score(\d+)-(\d+)", clave):
                limpio = re.sub(r"'''|&nbsp;", "", valor).strip()
                if limpio:
                    casilla = casillas.setdefault((int(r.group(1)), int(r.group(2))), {"puntuaciones": {}})
                    casilla["puntuaciones"][int(r.group(3))] = limpio
        for (ronda, posicion), a in sorted(casillas.items()):
            b = casillas.get((ronda, posicion + 1))
            if posicion % 2 == 0 or not b or not a.get("jugador") or not b.get("jugador"):
                continue
            nombre_ronda = rondas.get(ronda, "")
            yield RONDAS.get(nombre_ronda.lower(), nombre_ronda), a, b


def _datos_torneo(torneo):
    return {k: torneo[k] for k in ("circuito", "categoria", "superficie", "interior", "mejor_de")}


def partidos_pendientes(texto, torneo):
    """Partidos del cuadro con los dos jugadores decididos y sin marcador."""
    partidos = []
    for ronda, a, b in _partidos_del_cuadro(texto):
        if a["puntuaciones"] or b["puntuaciones"]:
            continue
        partidos.append({
            "id": f"{torneo['circuito']}-{torneo['nombre']}-{ronda}-{a['jugador']['nombre']}",
            "torneo": torneo["nombre"], "ciudad": torneo["ciudad"], **_datos_torneo(torneo),
            "ronda": ronda, "jugadores": [a["jugador"], b["jugador"]],
        })
    return partidos


ORDEN_RONDAS = {"1.ª ronda": 1, "2.ª ronda": 2, "3.ª ronda": 3, "4.ª ronda": 4, "Octavos": 4,
                "Cuartos de final": 5, "Semifinales": 6, "Final": 7}


def partidos_jugados(texto, torneo):
    """Partidos terminados del cuadro, con el marcador de cada set. Se descartan abandonos y
    walkovers. La fecha es aproximada: el inicio del torneo más lo que suele tardar esa ronda."""
    duracion = (torneo["fin"] - torneo["inicio"]).days
    partidos = []
    for ronda, a, b in _partidos_del_cuadro(texto):
        if not a["puntuaciones"] or not b["puntuaciones"] or a["gana"] == b["gana"]:
            continue
        valores = list(a["puntuaciones"].values()) + list(b["puntuaciones"].values())
        if any(re.search(r"r|w/o|def", v, re.I) for v in valores):
            continue
        sets = []
        for n in sorted(a["puntuaciones"]):
            ja = re.match(r"\d+", a["puntuaciones"][n])
            jb = re.match(r"\d+", b["puntuaciones"].get(n, ""))
            if not ja or not jb:
                break
            sets.append((int(ja.group()), int(jb.group())))
        ganador, perdedor = (a, b) if a["gana"] else (b, a)
        if ganador is b:
            sets = [(y, x) for x, y in sets]
        if not sets or sum(g > p for g, p in sets) <= len(sets) / 2:
            continue  # el marcador no cuadra con el ganador
        orden = ORDEN_RONDAS.get(ronda, 3)
        partidos.append({
            "fecha": torneo["inicio"] + timedelta(days=round(orden / 7 * duracion)),
            "torneo": torneo["nombre"], "superficie": torneo["superficie"], "ronda": ronda, "orden": orden,
            "ganador": ganador["jugador"]["nombre"], "perdedor": perdedor["jugador"]["nombre"],
            "alias": {j["nombre"]: j["alias"] for j in (a["jugador"], b["jugador"]) if j["alias"]},
            "sets": sets,
        })
    return partidos
