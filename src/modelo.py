"""Modelo de Poisson para estimar las probabilidades de cada partido.

Idea: cada equipo tiene una fuerza de ataque (goles que marca respecto a la media)
y de defensa (goles que recibe respecto a la media). Con ellas se estiman los goles
esperados de cada lado y, con la distribución de Poisson, la probabilidad de cada marcador.
"""
from datetime import datetime, timezone
from math import exp, factorial

MAX_GOLES = 10
VENTAJA_LOCAL = 1.12   # multiplicador de goles para el local (y divisor para el visitante)
PESO_PREVIO = 4        # partidos "virtuales" de nivel medio que suavizan muestras pequeñas
MEDIA_POR_DEFECTO = 1.4

ETAPAS = {
    "LEAGUE_STAGE": "Fase liga",
    "GROUP_STAGE": "Fase de grupos",
    "PLAYOFFS": "Play-off",
    "LAST_16": "Octavos de final",
    "QUARTER_FINALS": "Cuartos de final",
    "SEMI_FINALS": "Semifinales",
    "FINAL": "Final",
}


def _poisson(k, lam):
    return lam ** k * exp(-lam) / factorial(k)


def _resumen_equipo(equipo_id, partidos):
    gf = gc = 0
    ultimos = []
    for p in partidos:
        es_local = p["local"]["id"] == equipo_id
        a, b = (p["goles_local"], p["goles_visitante"]) if es_local else (p["goles_visitante"], p["goles_local"])
        gf += a
        gc += b
        rival = p["visitante"] if es_local else p["local"]
        ultimos.append({
            "fecha": p["fecha"],
            "rival": rival["corto"],
            "condicion": "L" if es_local else "V",
            "gf": a,
            "gc": b,
            "resultado": "G" if a > b else "E" if a == b else "P",
            "competicion": p["competicion"],
        })
    return {"n": len(partidos), "gf": gf, "gc": gc, "ultimos": ultimos}


def _media_goles(historiales):
    unicos = {p["id"]: p for partidos in historiales.values() for p in partidos}
    if not unicos:
        return MEDIA_POR_DEFECTO
    total = sum(p["goles_local"] + p["goles_visitante"] for p in unicos.values())
    return total / (2 * len(unicos))


def _fuerzas(resumen, media):
    n = resumen["n"]
    ataque = (resumen["gf"] + PESO_PREVIO * media) / (n + PESO_PREVIO) / media
    defensa = (resumen["gc"] + PESO_PREVIO * media) / (n + PESO_PREVIO) / media
    return ataque, defensa


def _pronostico(p1, px, p2, local, visitante):
    prob, texto, mercado = max([
        (p1, f"Gana {local}", "1"),
        (px, "Empate", "X"),
        (p2, f"Gana {visitante}", "2"),
    ])
    if prob < 0.45:  # partido muy abierto: mejor una doble oportunidad
        prob, texto, mercado = max([
            (p1 + px, f"{local} o empate", "1X"),
            (p2 + px, f"{visitante} o empate", "X2"),
        ])
    confianza = "alta" if prob >= 0.65 else "media" if prob >= 0.5 else "baja"
    return {"texto": texto, "mercado": mercado, "prob": prob, "confianza": confianza, "cuota_justa": 1 / prob}


def analizar_partido(partido, historiales, media):
    local, visitante = partido["local"], partido["visitante"]
    rl = _resumen_equipo(local["id"], historiales.get(local["id"], []))
    rv = _resumen_equipo(visitante["id"], historiales.get(visitante["id"], []))
    ataque_l, defensa_l = _fuerzas(rl, media)
    ataque_v, defensa_v = _fuerzas(rv, media)

    ventaja = 1.0 if partido["etapa"] == "FINAL" else VENTAJA_LOCAL  # la final es en campo neutral
    lam_l = media * ataque_l * defensa_v * ventaja
    lam_v = media * ataque_v * defensa_l / ventaja

    rango = range(MAX_GOLES + 1)
    matriz = {(i, j): _poisson(i, lam_l) * _poisson(j, lam_v) for i in rango for j in rango}
    total = sum(matriz.values())
    prob = {k: v / total for k, v in matriz.items()}

    p1 = sum(v for (i, j), v in prob.items() if i > j)
    px = sum(v for (i, j), v in prob.items() if i == j)
    p2 = sum(v for (i, j), v in prob.items() if i < j)
    mas_2_5 = sum(v for (i, j), v in prob.items() if i + j > 2)
    ambos = sum(v for (i, j), v in prob.items() if i > 0 and j > 0)
    marcadores = sorted(prob.items(), key=lambda kv: kv[1], reverse=True)[:3]

    def ficha(equipo, resumen):
        n = resumen["n"]
        return {
            **equipo,
            "partidos": n,
            "media_gf": resumen["gf"] / n if n else None,
            "media_gc": resumen["gc"] / n if n else None,
            "ultimos": resumen["ultimos"][-5:][::-1],  # el más reciente primero
        }

    return {
        "id": partido["id"],
        "fecha": partido["fecha"],
        "estado": partido["estado"],
        "equipos": {"local": ficha(local, rl), "visitante": ficha(visitante, rv)},
        "goles_esperados": {"local": lam_l, "visitante": lam_v},
        "probabilidades": {
            "local": p1, "empate": px, "visitante": p2,
            "mas_2_5": mas_2_5, "ambos_marcan": ambos,
        },
        "marcadores": [{"local": i, "visitante": j, "prob": p} for (i, j), p in marcadores],
        "pronostico": _pronostico(p1, px, p2, local["corto"], visitante["corto"]),
        "pronostico_goles": (
            {"texto": "Más de 2.5 goles", "prob": mas_2_5} if mas_2_5 >= 0.5
            else {"texto": "Menos de 2.5 goles", "prob": 1 - mas_2_5}
        ),
    }


def nombre_jornada(partido):
    etapa = ETAPAS.get(partido["etapa"], partido["etapa"] or "")
    if partido["jornada"] is not None and partido["etapa"] in ("LEAGUE_STAGE", "GROUP_STAGE"):
        return f"{etapa} · Jornada {partido['jornada']}"
    return etapa


def analizar_jornada(partidos, historiales):
    media = _media_goles(historiales)
    partidos = sorted(partidos, key=lambda p: p["fecha"])
    return {
        "competicion": "UEFA Champions League",
        "jornada": nombre_jornada(partidos[0]) if partidos else "",
        "generado": datetime.now(timezone.utc).isoformat(),
        "media_goles": media,
        "partidos": [analizar_partido(p, historiales, media) for p in partidos],
    }
