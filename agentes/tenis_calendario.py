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
    valor = valor.replace("'''", "")
    enlace = ENLACE.search(valor)
    if not enlace:
        return None
    pais = PAIS.search(valor)
    return {"nombre": re.sub(r"\s*\([^)]*\)", "", enlace.group(1)).strip(), "pais": pais.group(1) if pais else ""}


def partidos_pendientes(texto, torneo):
    """Partidos del cuadro con los dos jugadores decididos y sin marcador."""
    corte = re.search(r"^==+\s*Qualif", texto, re.M)
    texto = re.sub(r"<!--.*?-->", "", texto[:corte.start()] if corte else texto, flags=re.S)
    partidos = []
    for bloque in _plantillas_cuadro(texto):
        parametros = {}
        for linea in bloque.splitlines():
            m = re.match(r"\s*\|\s*(RD\d+(?:-[a-z]+\d+(?:-\d+)?)?)\s*=\s*(.*)$", linea)
            if m:
                parametros[m.group(1)] = m.group(2).strip()
        rondas, jugadores, con_marcador = {}, {}, set()
        for clave, valor in parametros.items():
            if m := re.fullmatch(r"RD(\d+)", clave):
                rondas[int(m.group(1))] = _limpiar(valor)
            elif m := re.fullmatch(r"RD(\d+)-team(\d+)", clave):
                if jugador := _jugador(valor):
                    jugadores[(int(m.group(1)), int(m.group(2)))] = jugador
            elif m := re.fullmatch(r"RD(\d+)-score(\d+)-\d+", clave):
                if re.sub(r"'''|&nbsp;|<[^>]+>", "", valor).strip():
                    con_marcador.add((int(m.group(1)), int(m.group(2))))
        for (ronda, posicion), a in sorted(jugadores.items()):
            b = jugadores.get((ronda, posicion + 1))
            if posicion % 2 == 0 or not b or {(ronda, posicion), (ronda, posicion + 1)} & con_marcador:
                continue
            nombre_ronda = rondas.get(ronda, "")
            partidos.append({
                "id": f"{torneo['circuito']}-{torneo['nombre']}-{nombre_ronda}-{a['nombre']}",
                "torneo": torneo["nombre"], "ciudad": torneo["ciudad"], "circuito": torneo["circuito"],
                "categoria": torneo["categoria"], "superficie": torneo["superficie"],
                "interior": torneo["interior"], "mejor_de": torneo["mejor_de"],
                "ronda": RONDAS.get(nombre_ronda.lower(), nombre_ronda),
                "jugadores": [a, b],
            })
    return partidos
