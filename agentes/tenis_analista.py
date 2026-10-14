"""Agente Tenis-Analista: probabilidades de cada partido de tenis.

1. Calcula un ranking Elo de cada jugador con todos sus resultados recientes, uno general
   y otro por superficie (dura, tierra, hierba).
2. Del Elo sale la probabilidad de ganar el partido.
3. Con ella se ajusta el modelo juego a juego (tenis_modelo) para obtener sets exactos,
   total de juegos y probabilidad de tie-break.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from .base import Agente
from .tenis_modelo import distribucion_partido, saques_para

ELO_INICIAL = 1500
ELO_DESCONOCIDO = 1400   # jugador sin resultados en la base de datos
PARTIDOS_SUPERFICIE_PLENA = 20
EXTRA_INTERIOR = 0.01
LINEAS_JUEGOS = {3: (20.5, 22.5, 24.5), 5: (34.5, 37.5, 40.5)}
MIN_PARTIDOS_FIABLE = 10


def _k(partidos_jugados):
    return 250 / (partidos_jugados + 5) ** 0.4


def calcular_elo(partidos):
    """Recorre los partidos en orden. Guarda en cada uno la probabilidad que el Elo daba al
    favorito antes de jugarse ("prob_favorito"), que sirve para calibrar el modelo."""
    general, superficie = defaultdict(lambda: ELO_INICIAL), defaultdict(lambda: ELO_INICIAL)
    jugados_g, jugados_s = Counter(), Counter()
    for p in partidos:
        g, l, s = p["ganador"], p["perdedor"], p["superficie"]
        previa = 1 / (1 + 10 ** ((general[l] - general[g]) / 400))
        p["prob_favorito"] = max(previa, 1 - previa)
        p["gano_favorito"] = previa >= 0.5
        for tabla, jugados, kg, kl in ((general, jugados_g, g, l), (superficie, jugados_s, (g, s), (l, s))):
            esperado = 1 / (1 + 10 ** ((tabla[kl] - tabla[kg]) / 400))
            tabla[kg] += _k(jugados[kg]) * (1 - esperado)
            tabla[kl] -= _k(jugados[kl]) * (1 - esperado)
            jugados[kg] += 1
            jugados[kl] += 1
    return general, superficie, jugados_g, jugados_s


def _modelo_medio(base, mezcla):
    """Juegos y % de tie-break medios que da el modelo para una mezcla de partidos
    {probabilidad del favorito: peso}."""
    juegos = tiebreak = 0.0
    total = sum(mezcla.values())
    for prob, peso in mezcla.items():
        for (_, _, j, tb), p in distribucion_partido(*saques_para(prob, base)).items():
            juegos += peso * p * j
            tiebreak += peso * p * tb
    return juegos / total, tiebreak / total


def calibrar(real):
    """1. Probabilidad media de ganar el saque con la que el modelo reproduce el % real de
          tie-breaks (lo que mejor refleja cuánto domina el saque).
       2. Corrección de juegos: el modelo supone que cada juego es independiente y da partidos
          algo más largos que los reales, así que se suma la diferencia de medias."""
    bajo, alto = 0.60, 0.95
    for _ in range(14):
        base = (bajo + alto) / 2
        if _modelo_medio(base, real["mezcla"])[1] < real["tiebreak"]:
            bajo = base
        else:
            alto = base
    base = (bajo + alto) / 2
    juegos_modelo, tiebreak_modelo = _modelo_medio(base, real["mezcla"])
    return base, real["juegos"] - juegos_modelo, tiebreak_modelo


def estadisticas_reales(partidos, desde):
    """Por superficie, para los partidos al mejor de 3 desde una fecha: media real de juegos,
    % real de tie-break y mezcla de probabilidades del favorito (en tramos de 5 puntos)."""
    grupos = defaultdict(list)
    for p in partidos:
        if p["fecha"] >= desde and sum(g > l for g, l in p["sets"]) == 2:
            grupos[p["superficie"]].append(p)
    resultado = {}
    for sup, lista in grupos.items():
        if len(lista) < 50:
            continue
        mezcla = Counter(min(0.975, round(p["prob_favorito"] * 20) / 20 + 0.025) for p in lista)
        resultado[sup] = {
            "partidos": len(lista), "mezcla": mezcla,
            "juegos": sum(sum(g + l for g, l in p["sets"]) for p in lista) / len(lista),
            "tiebreak": sum(any(g + l == 13 for g, l in p["sets"]) for p in lista) / len(lista),
        }
    return resultado


def _corto(nombre, alias=""):
    """Nombre corto: "A. Zverev". Los cuadros de Wikipedia ya lo traen como "A Zverev" (o
    "Q Zheng" para nombres asiáticos); si no, se forma con la inicial y el resto del nombre."""
    if alias:
        inicial, _, resto = alias.partition(" ")
        if resto and len(inicial) <= 3 and inicial[:1].isupper():
            return f"{inicial}. {resto}"
        return alias
    palabras = nombre.split()
    return f"{palabras[0][0]}. {' '.join(palabras[1:])}" if len(palabras) > 1 else nombre


class AgenteTenisAnalista(Agente):
    nombre = "tenis-analista"

    def trabajar(self, calendario, resultados, mapa):
        hoy = datetime.now(timezone.utc).date()
        elos, calibracion = {}, {}
        circuitos = {p["circuito"] for p in calendario["partidos"]}
        self.alias = resultados["alias"]
        for circuito, partidos in resultados["partidos"].items():
            elos[circuito] = calcular_elo(partidos)
            general = elos[circuito][0]
            mejores = sorted(general.items(), key=lambda kv: kv[1], reverse=True)[:3]
            self.info(f"Elo {circuito}: {len(general)} jugadores. Top 3: "
                      + ", ".join(f"{n} ({e:.0f})" for n, e in mejores))
            ultimo_anio = [p for p in partidos if p["fecha"] >= hoy - timedelta(days=365)]
            if ultimo_anio:
                acierto = sum(p["gano_favorito"] for p in ultimo_anio) / len(ultimo_anio)
                self.info(f"Elo {circuito}: el favorito ganó el {acierto:.0%} de los {len(ultimo_anio)} "
                          "partidos del último año (comprobado antes de cada partido)")
            if circuito not in circuitos:
                continue
            for sup, real in estadisticas_reales(partidos, hoy - timedelta(days=365)).items():
                base, correccion, tiebreak_modelo = calibrar(real)
                calibracion[(circuito, sup)] = (base, correccion)
                self.info(f"Calibrado {circuito} {sup} con {real['partidos']} partidos: saque ganado el "
                          f"{base:.0%}, tie-break {tiebreak_modelo:.0%} (real {real['tiebreak']:.0%}), "
                          f"corrección de juegos {correccion:+.1f} (media real {real['juegos']:.1f})")

        analizados = []
        for partido in calendario["partidos"]:
            circuito, sup = partido["circuito"], partido["superficie"]
            fichas = [self._ficha(j, mapa.get(f"{circuito}|{j['nombre']}"), resultados["partidos"][circuito],
                                  elos[circuito], sup, hoy) for j in partido["jugadores"]]
            a, b = fichas
            prob_a = 1 / (1 + 10 ** ((b["elo"] - a["elo"]) / 400))
            base, correccion = calibracion.get((circuito, sup)) or calibracion.get((circuito, "Hard"), (0.75, 0.0))
            base += EXTRA_INTERIOR if partido["interior"] else 0
            ha, hb = saques_para(prob_a, base)
            # la corrección se calibró al mejor de 3; al mejor de 5 se escala por el número de sets
            analisis = _analizar(partido, fichas, ha, hb, correccion * partido["mejor_de"] / 3)
            analizados.append(analisis)
            self.info(f"{partido['torneo']} · {a['corto']} vs {b['corto']}: "
                      f"{analisis['prob']['a']:.0%} - {analisis['prob']['b']:.0%} | "
                      f"{analisis['juegos']['esperados']:.1f} juegos | tie-break {analisis['tiebreak']:.0%}")

        confianza = [p["pronostico"]["confianza"] for p in analizados]
        self.metricas = {"partidos": len(analizados),
                         **{f"confianza_{n}": confianza.count(n) for n in ("alta", "media", "baja")}}
        return {"generado": datetime.now(timezone.utc).isoformat(), "torneos": calendario["torneos"],
                "partidos": analizados}

    def _ficha(self, jugador, nombre_td, partidos, elo, superficie, hoy):
        general, por_superficie, jugados_g, jugados_s = elo
        propios = [p for p in partidos if nombre_td in (p["ganador"], p["perdedor"])] if nombre_td else []
        ultimo_anio = [p for p in propios if p["fecha"] >= hoy - timedelta(days=365)]
        en_superficie = [p for p in ultimo_anio if p["superficie"] == superficie]

        if nombre_td and jugados_g[nombre_td]:
            peso = 0.5 * min(1, jugados_s[(nombre_td, superficie)] / PARTIDOS_SUPERFICIE_PLENA)
            valor = (1 - peso) * general[nombre_td] + peso * por_superficie[(nombre_td, superficie)]
        else:
            valor = ELO_DESCONOCIDO
        if len(ultimo_anio) < MIN_PARTIDOS_FIABLE:
            self.aviso(f"{jugador['nombre']}: solo {len(ultimo_anio)} partidos en el último año")

        ultimos = []
        for p in propios[-5:][::-1]:
            gano = p["ganador"] == nombre_td
            ultimos.append({
                "fecha": p["fecha"].isoformat(), "torneo": p["torneo"],
                "rival": _corto(rival := p["perdedor"] if gano else p["ganador"], self.alias.get(rival, "")),
                "resultado": "G" if gano else "P",
                "marcador": " ".join(f"{g}-{l}" if gano else f"{l}-{g}" for g, l in p["sets"]),
            })
        palabras = jugador["nombre"].replace("-", " ").split()
        return {
            "nombre": jugador["nombre"],
            "corto": _corto(jugador["nombre"], jugador.get("alias") or self.alias.get(nombre_td or "", "")),
            "tla": "".join(p[0] for p in palabras[:3]).upper(), "pais": jugador["pais"],
            "elo": valor,
            "elo_general": general[nombre_td] if nombre_td else None,
            "elo_superficie": por_superficie[(nombre_td, superficie)] if nombre_td else None,
            "partidos_anio": len(ultimo_anio),
            "victorias_anio": sum(p["ganador"] == nombre_td for p in ultimo_anio) / len(ultimo_anio) if ultimo_anio else None,
            "partidos_superficie": len(en_superficie),
            "victorias_superficie": sum(p["ganador"] == nombre_td for p in en_superficie) / len(en_superficie) if en_superficie else None,
            "ultimos": ultimos,
        }


def _mas_de(por_juegos, umbral):
    """P(juegos > umbral), interpolando entre enteros para que la corrección no dé saltos."""
    def mayor_que(n):
        return sum(p for j, p in por_juegos.items() if j > n)
    abajo = int(umbral // 1)
    fraccion = umbral - abajo
    return (1 - fraccion) * mayor_que(abajo) + fraccion * mayor_que(abajo + 1)


def _analizar(partido, fichas, ha, hb, correccion_juegos):
    mejor_de = partido["mejor_de"]
    necesarios = mejor_de // 2 + 1
    distribucion = distribucion_partido(ha, hb, mejor_de)

    por_sets, por_juegos = Counter(), Counter()
    tiebreak = decisivo = 0.0
    for (sa, sb, juegos, hubo_tb), p in distribucion.items():
        por_sets[(sa, sb)] += p
        por_juegos[juegos] += p
        tiebreak += p * hubo_tb
        decisivo += p * (sa + sb == mejor_de)
    prob_a = sum(p for (sa, _), p in por_sets.items() if sa == necesarios)
    sets = [{"a": sa, "b": sb, "prob": por_sets[(sa, sb)]}
            for sa, sb in [(necesarios, x) for x in range(necesarios)] + [(x, necesarios) for x in reversed(range(necesarios))]]
    lineas = [{"linea": l, "mas": _mas_de(por_juegos, l - correccion_juegos)} for l in LINEAS_JUEGOS[mejor_de]]

    a, b = fichas
    favorito, prob = (a, prob_a) if prob_a >= 0.5 else (b, 1 - prob_a)
    sets_probable = max(sets, key=lambda s: s["prob"])
    return {
        "id": partido["id"], "torneo": partido["torneo"], "ciudad": partido["ciudad"],
        "circuito": partido["circuito"], "categoria": partido["categoria"],
        "superficie": partido["superficie"], "interior": partido["interior"],
        "ronda": partido["ronda"], "mejor_de": mejor_de,
        "jugadores": {"a": a, "b": b},
        "prob": {"a": prob_a, "b": 1 - prob_a},
        "saque": {"a": ha, "b": hb},
        "sets": sets,
        "juegos": {"esperados": sum(j * p for j, p in por_juegos.items()) + correccion_juegos, "lineas": lineas},
        "tiebreak": tiebreak,
        "decisivo": decisivo,
        "pronostico": {
            "texto": f"Gana {favorito['corto']}", "prob": prob, "cuota_justa": 1 / prob,
            "confianza": "alta" if prob >= 0.75 else "media" if prob >= 0.62 else "baja",
            "sets": f"{sets_probable['a']}-{sets_probable['b']}", "prob_sets": sets_probable["prob"],
        },
        "fiable": all(f["partidos_anio"] >= MIN_PARTIDOS_FIABLE for f in fichas),
    }
