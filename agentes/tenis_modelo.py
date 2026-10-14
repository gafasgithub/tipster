"""Modelo de un partido de tenis, juego a juego.

Cada jugador tiene una probabilidad de ganar un juego con su saque. A partir de ahí
se calcula, sin simulaciones aleatorias, la probabilidad exacta de cada marcador de
set, de cada resultado en sets y del número total de juegos.
"""
from collections import defaultdict
from functools import lru_cache

MIN_SAQUE, MAX_SAQUE = 0.40, 0.97


def prob_juego(p):
    """Probabilidad de ganar un juego al saque si se gana cada punto con probabilidad p."""
    q = 1 - p
    return p ** 4 * (1 + 4 * q + 10 * q * q) + 20 * p ** 3 * q ** 3 * (p * p / (1 - 2 * p * q))


def punto_desde_juego(prob):
    """Inversa de prob_juego, por bisección."""
    bajo, alto = 0.01, 0.99
    for _ in range(50):
        medio = (bajo + alto) / 2
        bajo, alto = (medio, alto) if prob_juego(medio) < prob else (bajo, medio)
    return (bajo + alto) / 2


def prob_tiebreak(pa, pb):
    """A saca primero. pa / pb: probabilidad de ganar un punto con el propio saque."""
    @lru_cache(maxsize=None)
    def desde(a, b):
        if a >= 7 and a - b >= 2:
            return 1.0
        if b >= 7 and b - a >= 2:
            return 0.0
        if a == b and a >= 6:  # a partir de 6-6, cada par de puntos lo saca uno de cada
            gana, pierde = pa * (1 - pb), (1 - pa) * pb
            return gana / (gana + pierde)
        saca_a = ((a + b + 1) // 2) % 2 == 0
        p = pa if saca_a else 1 - pb
        return p * desde(a + 1, b) + (1 - p) * desde(a, b + 1)
    return desde(0, 0)


def distribucion_set(ha, hb, tiebreak_a):
    """{(juegos A, juegos B): probabilidad}, con A sacando el primer juego."""
    finales, estados = defaultdict(float), {(0, 0): 1.0}
    while estados:
        nuevos = defaultdict(float)
        for (a, b), prob in estados.items():
            if a == b == 6:
                finales[(7, 6)] += prob * tiebreak_a
                finales[(6, 7)] += prob * (1 - tiebreak_a)
                continue
            gana = ha if (a + b) % 2 == 0 else 1 - hb
            for (na, nb), p in (((a + 1, b), gana), ((a, b + 1), 1 - gana)):
                if 7 in (na, nb) or (max(na, nb) >= 6 and abs(na - nb) >= 2):
                    finales[(na, nb)] += prob * p
                else:
                    nuevos[(na, nb)] += prob * p
        estados = nuevos
    return finales


def distribucion_partido(ha, hb, mejor_de=3):
    """{(sets A, sets B, juegos totales, hubo tie-break): probabilidad}"""
    pa, pb = punto_desde_juego(ha), punto_desde_juego(hb)
    saca_a = distribucion_set(ha, hb, prob_tiebreak(pa, pb))
    saca_b = {(a, b): p for (b, a), p in distribucion_set(hb, ha, prob_tiebreak(pb, pa)).items()}
    # Quién saca primero en cada set depende del anterior: se promedian ambos casos
    por_set = {k: (saca_a.get(k, 0) + saca_b.get(k, 0)) / 2 for k in set(saca_a) | set(saca_b)}

    necesarios = mejor_de // 2 + 1
    finales, estados = defaultdict(float), {(0, 0, 0, False): 1.0}
    while estados:
        nuevos = defaultdict(float)
        for (sa, sb, juegos, tiebreak), prob in estados.items():
            for (ga, gb), p in por_set.items():
                clave = (sa + (ga > gb), sb + (gb > ga), juegos + ga + gb, tiebreak or ga + gb == 13)
                destino = finales if necesarios in clave[:2] else nuevos
                destino[clave] += prob * p
        estados = nuevos
    return finales


def prob_victoria(ha, hb, mejor_de=3):
    return sum(p for (sa, _, _, _), p in distribucion_partido(ha, hb, mejor_de).items() if sa > mejor_de // 2)


def saques_para(prob_objetivo, base):
    """Busca las probabilidades de ganar el saque (base ± d) que dan prob_objetivo al mejor de 3."""
    bajo, alto = -0.35, 0.35
    for _ in range(30):
        d = (bajo + alto) / 2
        ha = min(MAX_SAQUE, max(MIN_SAQUE, base + d))
        hb = min(MAX_SAQUE, max(MIN_SAQUE, base - d))
        bajo, alto = (d, alto) if prob_victoria(ha, hb) < prob_objetivo else (bajo, d)
    d = (bajo + alto) / 2
    return min(MAX_SAQUE, max(MIN_SAQUE, base + d)), min(MAX_SAQUE, max(MIN_SAQUE, base - d))
