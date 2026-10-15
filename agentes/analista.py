"""Agente Analista: calcula las probabilidades de goles, corners y tarjetas.

Para cada equipo junta sus partidos de liga (football-data.co.uk) y de la competición
europea que juega (Champions o Europa League, de Wikipedia). Los de liga se ajustan al nivel de cada liga, para que dominar la liga
eslovaca no cuente igual que dominar la Premier League.
"""
from datetime import datetime, timezone

from src.modelo import MAX_GOLES, VENTAJA_LOCAL, _poisson, _pronostico, nombre_jornada

from .base import Agente

# Nivel de cada liga respecto a un equipo medio de Champions (1.0). Aproximado,
# inspirado en el coeficiente UEFA. Multiplica el ataque y divide la defensa.
NIVEL_LIGA = {
    "ENG": 1.18, "ESP": 1.10, "ITA": 1.08, "GER": 1.06, "FRA": 1.00, "POR": 0.92, "NED": 0.90,
    "BEL": 0.86, "TUR": 0.84, "GRE": 0.80, "AUT": 0.80, "CZE": 0.80, "SUI": 0.80, "SCO": 0.78,
    "DEN": 0.78, "UKR": 0.78, "NOR": 0.76, "CRO": 0.74, "SRB": 0.74, "POL": 0.74, "SWE": 0.72,
    "ISR": 0.70, "CYP": 0.70, "SVK": 0.68, "HUN": 0.68, "ROU": 0.68, "AZE": 0.66, "BUL": 0.64,
    "SLO": 0.62, "KAZ": 0.62, "MDA": 0.60, "ARM": 0.58,
}
NIVEL_DESCONOCIDO = 0.72
COMPRESION = 0.65         # suaviza lo mucho que domina un equipo en una liga débil
PESO_COPA = 1.5           # un partido de Champions o Europa League cuenta 1.5 veces uno de liga
PESO_PREVIO = 4           # partidos "virtuales" al nivel de su liga, para muestras pequeñas
MAX_PARTIDOS_LIGA = 12
MEDIA_COPA_PREVIA = 1.45  # goles por equipo antes de que se jueguen partidos
# Estadísticas por equipo y partido: valor medio si no hay datos, y líneas de "más de"
ESTADISTICAS = {
    "corners": {"defecto": 5.0, "lineas": (8.5, 9.5, 10.5)},
    "tarjetas": {"defecto": 2.0, "lineas": (3.5, 4.5, 5.5)},
    "tiros": {"defecto": 12.5, "lineas": (22.5, 24.5, 26.5)},
    "apuerta": {"defecto": 4.3, "lineas": (7.5, 8.5, 9.5)},
    "faltas": {"defecto": 11.5, "lineas": (20.5, 22.5, 24.5)},
}
MIN_PARTIDOS_FIABLE = 5


def _media(valores):
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


class AgenteAnalista(Agente):
    nombre = "analista"

    def trabajar(self, calendario, ligas, mapa):
        resultado, self.metricas = {}, {}
        for clave, competicion in calendario["competiciones"].items():
            resultado[clave] = self._competicion(competicion, ligas, mapa)
            self.metricas[clave] = resultado[clave].pop("metricas")
        return resultado

    def _competicion(self, competicion, ligas, mapa):
        jugados, proximos, corto = competicion["jugados"], competicion["proximos"], competicion["corto"]
        goles = sum(p["goles_local"] + p["goles_visitante"] for p in jugados)
        media = (goles + MEDIA_COPA_PREVIA * 36) / (2 * len(jugados) + 36)
        self.info(f"Media de goles por equipo en esta {corto}: {media:.2f} ({len(jugados)} partidos jugados)")

        partidos = []
        for p in sorted(proximos, key=lambda p: p["fecha"]):
            fichas = {lado: self._ficha(p[lado], jugados, ligas, mapa, media, corto) for lado in ("local", "visitante")}
            analisis = _analizar(p, fichas, media)
            partidos.append(analisis)
            pr, c, t = analisis["probabilidades"], analisis["mercados"]["corners"], analisis["mercados"]["tarjetas"]
            self.info(f"{p['local']['corto']} vs {p['visitante']['corto']}: "
                      f"1 {pr['local']:.0%} · X {pr['empate']:.0%} · 2 {pr['visitante']:.0%} | "
                      f"corners {c['total']:.1f} | tarjetas {t['total']:.1f}")

        confianza = [p["pronostico"]["confianza"] for p in partidos]
        return {
            "competicion": competicion["nombre"],
            "jornada": nombre_jornada(proximos[0]) if proximos else "",
            "generado": datetime.now(timezone.utc).isoformat(),
            "media_goles": media,
            "partidos": partidos,
            "metricas": {
                "partidos": len(partidos), "media_goles": round(media, 2),
                **{f"confianza_{n}": confianza.count(n) for n in ("alta", "media", "baja")},
            },
        }

    def _ficha(self, equipo, jugados, ligas, mapa, media, corto):
        nivel = NIVEL_LIGA.get(equipo["pais"], NIVEL_DESCONOCIDO)
        registros = []
        for p in jugados:
            if equipo["id"] not in (p["local"]["id"], p["visitante"]["id"]):
                continue
            es_local = p["local"]["id"] == equipo["id"]
            registros.append(_registro(
                p["fecha"][:10], (p["visitante"] if es_local else p["local"])["corto"], es_local,
                p["goles_local"], p["goles_visitante"], corto, "copa"))

        destino = mapa.get(equipo["id"])
        liga = ligas.get(equipo["pais"]) if destino else None
        if liga:
            propios = [m for m in liga["partidos"] if destino["nombre"] in (m["local"], m["visitante"])]
            for m in propios[-MAX_PARTIDOS_LIGA:]:
                es_local = m["local"] == destino["nombre"]
                registros.append(_registro(
                    m["fecha"].isoformat(), m["visitante"] if es_local else m["local"], es_local,
                    m["gl"], m["gv"], liga["nombre"], "liga", m))

        de_liga = [r for r in registros if r["tipo"] == "liga"]
        de_copa = [r for r in registros if r["tipo"] == "copa"]
        componentes = [(nivel, 1 / nivel, PESO_PREVIO)]
        if de_liga:
            a_favor = _media((0.5 * r["gf"] + 0.5 * r["xgf"]) if r["xgf"] is not None else r["gf"] for r in de_liga)
            en_contra = _media((0.5 * r["gc"] + 0.5 * r["xgc"]) if r["xgc"] is not None else r["gc"] for r in de_liga)
            componentes.append((
                nivel * (a_favor / liga["media_goles"]) ** COMPRESION,
                (en_contra / liga["media_goles"]) ** COMPRESION / nivel,
                len(de_liga),
            ))
        if de_copa:
            componentes.append((
                _media(r["gf"] for r in de_copa) / media,
                _media(r["gc"] for r in de_copa) / media,
                PESO_COPA * len(de_copa),
            ))
        peso_total = sum(w for _, _, w in componentes)
        if len(de_liga) + len(de_copa) < 4:
            self.aviso(f"{equipo['nombre']}: solo {len(de_liga) + len(de_copa)} partidos, pronóstico poco fiable")

        def estadistica(nombre):
            con_dato = [r["stats"][nombre] for r in de_liga if r["stats"][nombre][0] is not None]
            if not con_dato:
                defecto = ESTADISTICAS[nombre]["defecto"]
                return {"a_favor": defecto, "en_contra": defecto, "n": 0}
            return {
                "a_favor": _media(favor for favor, _ in con_dato),
                "en_contra": _media(contra for _, contra in con_dato),
                "n": len(con_dato),
            }

        registros.sort(key=lambda r: r["fecha"], reverse=True)
        return {
            **equipo,
            "liga": liga["nombre"] if liga else None,
            "nivel": nivel,
            "ataque": sum(a * w for a, _, w in componentes) / peso_total,
            "defensa": sum(d * w for _, d, w in componentes) / peso_total,
            "datos": {"liga": len(de_liga), "copa": len(de_copa), "competicion": corto},
            "partidos": len(registros),
            "media_gf": _media(r["gf"] for r in registros),
            "media_gc": _media(r["gc"] for r in registros),
            "ultimos": [{k: r[k] for k in ("fecha", "rival", "condicion", "gf", "gc", "resultado", "competicion")}
                        for r in registros[:5]],
            "estadisticas": {nombre: estadistica(nombre) for nombre in ESTADISTICAS},
        }


def _registro(fecha, rival, es_local, goles_local, goles_visitante, competicion, tipo, fila=None):
    gf, gc = (goles_local, goles_visitante) if es_local else (goles_visitante, goles_local)
    fila = fila or {}
    propio, ajeno = ("_l", "_v") if es_local else ("_v", "_l")
    return {
        "fecha": fecha, "rival": rival, "condicion": "L" if es_local else "V", "gf": gf, "gc": gc,
        "resultado": "G" if gf > gc else "E" if gf == gc else "P",
        "competicion": competicion, "tipo": tipo,
        "xgf": fila.get("xg" + propio), "xgc": fila.get("xg" + ajeno),
        "stats": {n: (fila.get(n + propio), fila.get(n + ajeno)) for n in ESTADISTICAS},
    }


def _mercado(local, visitante, nombre):
    a, b = local["estadisticas"][nombre], visitante["estadisticas"][nombre]
    lam_l = (a["a_favor"] + b["en_contra"]) / 2
    lam_v = (b["a_favor"] + a["en_contra"]) / 2
    total = lam_l + lam_v
    pl = [_poisson(k, lam_l) for k in range(40)]
    pv = [_poisson(k, lam_v) for k in range(40)]
    return {
        "esperados": {"local": lam_l, "visitante": lam_v},
        "total": total,
        "lineas": [{"linea": l, "mas": 1 - sum(_poisson(k, total) for k in range(int(l) + 1))}
                   for l in ESTADISTICAS[nombre]["lineas"]],
        "local_mas": sum(pl[i] * pv[j] for i in range(40) for j in range(i)),
        "visitante_mas": sum(pl[i] * pv[j] for j in range(40) for i in range(j)),
        "fiable": a["n"] >= MIN_PARTIDOS_FIABLE and b["n"] >= MIN_PARTIDOS_FIABLE,
    }


def _analizar(partido, fichas, media):
    local, visitante = fichas["local"], fichas["visitante"]
    ventaja = 1.0 if partido["etapa"] == "FINAL" else VENTAJA_LOCAL
    lam_l = media * local["ataque"] * visitante["defensa"] * ventaja
    lam_v = media * visitante["ataque"] * local["defensa"] / ventaja

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

    return {
        "id": partido["id"], "fecha": partido["fecha"], "estado": partido["estado"],
        "arbitro": partido.get("arbitro"),
        "equipos": fichas,
        "goles_esperados": {"local": lam_l, "visitante": lam_v},
        "probabilidades": {"local": p1, "empate": px, "visitante": p2, "mas_2_5": mas_2_5, "ambos_marcan": ambos},
        "marcadores": [{"local": i, "visitante": j, "prob": p} for (i, j), p in marcadores],
        "pronostico": _pronostico(p1, px, p2, local["corto"], visitante["corto"]),
        "pronostico_goles": (
            {"texto": "Más de 2.5 goles", "prob": mas_2_5} if mas_2_5 >= 0.5
            else {"texto": "Menos de 2.5 goles", "prob": 1 - mas_2_5}
        ),
        "mercados": {nombre: _mercado(local, visitante, nombre) for nombre in ESTADISTICAS},
    }
