"""Agente Ligas: descarga de football-data.co.uk los partidos de liga de cada país."""
import csv
import io
from datetime import date, datetime, timedelta, timezone

from .base import Agente

URL_PRINCIPAL = "https://www.football-data.co.uk/mmz4281/{temporada}/{codigo}.csv"
URL_EXTRA = "https://www.football-data.co.uk/new/{codigo}.csv"
DIAS_HISTORIAL = 400

# país (código de Wikipedia) -> (archivo, nombre de la liga)
# Ligas "principales": traen xG, tiros, corners y tarjetas.
LIGAS_PRINCIPALES = {
    "ENG": ("E0", "Premier League"), "ESP": ("SP1", "LaLiga"), "GER": ("D1", "Bundesliga"),
    "ITA": ("I1", "Serie A"), "FRA": ("F1", "Ligue 1"), "NED": ("N1", "Eredivisie"),
    "BEL": ("B1", "Pro League"), "POR": ("P1", "Liga Portugal"), "TUR": ("T1", "Süper Lig"),
    "GRE": ("G1", "Super League"), "SCO": ("SC0", "Premiership"),
}
# Ligas "extra": solo resultados.
LIGAS_EXTRA = {
    "AUT": ("AUT", "Bundesliga austriaca"), "NOR": ("NOR", "Eliteserien"),
    "SUI": ("SWZ", "Super League suiza"), "DEN": ("DNK", "Superliga danesa"),
    "POL": ("POL", "Ekstraklasa"), "SWE": ("SWE", "Allsvenskan"), "ROU": ("ROU", "Liga I"),
}


class AgenteLigas(Agente):
    nombre = "ligas"

    def trabajar(self, paises):
        hoy = datetime.now(timezone.utc).date()
        desde = hoy - timedelta(days=DIAS_HISTORIAL)
        ligas, sin_fuente = {}, []
        for pais in sorted(paises):
            if pais in LIGAS_PRINCIPALES:
                codigo, nombre = LIGAS_PRINCIPALES[pais]
                partidos = []
                for temporada, horas in ((_codigo_temporada(hoy, -1), 24 * 7), (_codigo_temporada(hoy, 0), 6)):
                    contenido = self.descargar(URL_PRINCIPAL.format(temporada=temporada, codigo=codigo), horas)
                    partidos += [_fila_principal(f) for f in _leer_csv(contenido)]
            elif pais in LIGAS_EXTRA:
                codigo, nombre = LIGAS_EXTRA[pais]
                contenido = self.descargar(URL_EXTRA.format(codigo=codigo))
                partidos = [_fila_extra(f) for f in _leer_csv(contenido)]
            else:
                sin_fuente.append(pais)
                continue

            partidos = sorted((p for p in partidos if p and p["fecha"] >= desde), key=lambda p: p["fecha"])
            if not partidos:
                self.aviso(f"{nombre}: el archivo no trae partidos recientes")
                continue
            media = sum(p["gl"] + p["gv"] for p in partidos) / (2 * len(partidos))
            ligas[pais] = {
                "pais": pais, "codigo": codigo, "nombre": nombre, "partidos": partidos, "media_goles": media,
                "equipos": sorted({p["local"] for p in partidos} | {p["visitante"] for p in partidos}),
                "con_estadisticas": any(p.get("corners_l") is not None for p in partidos),
            }
            self.info(f"{nombre}: {len(partidos)} partidos, {len(ligas[pais]['equipos'])} equipos, "
                      f"{media:.2f} goles por equipo")

        if sin_fuente:
            self.aviso(f"Sin fuente de liga para: {', '.join(sin_fuente)} (solo se usarán sus partidos europeos)")
        self.metricas = {
            "ligas": len(ligas), "partidos": sum(len(l["partidos"]) for l in ligas.values()),
            "paises_sin_fuente": sin_fuente,
        }
        return ligas


def _codigo_temporada(hoy, desplazamiento):
    anio = (hoy.year if hoy.month >= 7 else hoy.year - 1) + desplazamiento
    return f"{anio % 100:02d}{(anio + 1) % 100:02d}"


def _leer_csv(contenido):
    if not contenido:
        return []
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
    return list(csv.DictReader(io.StringIO(texto)))


def _num(fila, clave):
    valor = (fila.get(clave) or "").strip()
    try:
        return float(valor) if valor else None
    except ValueError:
        return None


def _fecha(texto):
    dia, mes, anio = (int(x) for x in texto.strip().split("/"))
    return date(anio + 2000 if anio < 100 else anio, mes, dia)


def _tarjetas(amarillas, rojas):
    return None if amarillas is None else amarillas + (rojas or 0)


def _fila_principal(f):
    gl, gv = _num(f, "FTHG"), _num(f, "FTAG")
    if gl is None or gv is None or not f.get("HomeTeam") or not f.get("Date"):
        return None
    return {
        "fecha": _fecha(f["Date"]), "local": f["HomeTeam"].strip(), "visitante": f["AwayTeam"].strip(),
        "gl": int(gl), "gv": int(gv), "xg_l": _num(f, "HxG"), "xg_v": _num(f, "AxG"),
        "corners_l": _num(f, "HC"), "corners_v": _num(f, "AC"),
        "tarjetas_l": _tarjetas(_num(f, "HY"), _num(f, "HR")),
        "tarjetas_v": _tarjetas(_num(f, "AY"), _num(f, "AR")),
        "tiros_l": _num(f, "HS"), "tiros_v": _num(f, "AS"),
        "apuerta_l": _num(f, "HST"), "apuerta_v": _num(f, "AST"),
        "faltas_l": _num(f, "HF"), "faltas_v": _num(f, "AF"),
    }


def _fila_extra(f):
    gl, gv = _num(f, "HG"), _num(f, "AG")
    if gl is None or gv is None or not f.get("Home") or not f.get("Date"):
        return None
    return {
        "fecha": _fecha(f["Date"]), "local": f["Home"].strip(), "visitante": f["Away"].strip(),
        "gl": int(gl), "gv": int(gv), "xg_l": None, "xg_v": None,
    }
