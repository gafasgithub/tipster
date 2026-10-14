"""Datos de ejemplo (inventados) para probar la web sin clave de API."""
import random
from datetime import datetime, timedelta, timezone
from math import exp

# nombre, abreviatura, ataque, defensa (1 = nivel medio; defensa < 1 = recibe menos)
EQUIPOS = [
    ("Real Madrid", "RMA", 1.45, 0.80), ("Man City", "MCI", 1.40, 0.85),
    ("Bayern", "FCB", 1.55, 0.90), ("PSG", "PSG", 1.35, 0.85),
    ("Inter", "INT", 1.20, 0.70), ("Arsenal", "ARS", 1.30, 0.70),
    ("Barcelona", "BAR", 1.50, 1.00), ("Liverpool", "LIV", 1.40, 0.85),
    ("Leverkusen", "B04", 1.15, 1.00), ("Atlético", "ATM", 1.05, 0.80),
    ("Dortmund", "BVB", 1.15, 1.10), ("Benfica", "SLB", 1.00, 1.05),
]
RIVALES = [("Celtic", "CEL"), ("Brujas", "BRU"), ("Feyenoord", "FEY"), ("Sporting", "SCP"),
           ("Salzburgo", "RBS"), ("Young Boys", "YB"), ("Girona", "GIR"), ("Mónaco", "MON")]
MEDIA = 1.4


def _poisson(rng, lam):
    limite, k, p = exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def _equipo(i, nombre, tla):
    return {"id": i, "nombre": nombre, "corto": nombre, "tla": tla, "escudo": ""}


def generar(semilla=7):
    rng = random.Random(semilla)
    ahora = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    equipos = {i + 1: (_equipo(i + 1, n, t), at, de) for i, (n, t, at, de) in enumerate(EQUIPOS)}
    rivales = [(_equipo(100 + i, n, t), 1.0, 1.0) for i, (n, t) in enumerate(RIVALES)]
    siguiente_id = 1000

    historiales = {}
    for eid, (eq, at, de) in equipos.items():
        partidos = []
        for k in range(8):
            rival, at_r, de_r = rng.choice(rivales)
            casa = k % 2 == 0
            gl = _poisson(rng, MEDIA * (at if casa else at_r) * (de_r if casa else de))
            gv = _poisson(rng, MEDIA * (at_r if casa else at) * (de if casa else de_r))
            siguiente_id += 1
            partidos.append({
                "id": siguiente_id,
                "fecha": (ahora - timedelta(days=7 * (8 - k))).isoformat(),
                "estado": "FINISHED", "etapa": "LEAGUE_STAGE", "jornada": None,
                "competicion": "Ejemplo",
                "local": eq if casa else rival, "visitante": rival if casa else eq,
                "goles_local": gl, "goles_visitante": gv,
            })
        historiales[eid] = partidos

    ids = list(equipos)
    rng.shuffle(ids)
    proximos = []
    for n in range(len(ids) // 2):
        dia = 1 if n < 3 else 2
        hora = 17 if n % 3 == 0 else 20
        fecha = (ahora + timedelta(days=dia)).replace(hour=hora, minute=0 if hora == 20 else 45)
        proximos.append({
            "id": 500 + n, "fecha": fecha.isoformat(), "estado": "TIMED",
            "etapa": "LEAGUE_STAGE", "jornada": 4, "competicion": "UEFA Champions League",
            "local": equipos[ids[2 * n]][0], "visitante": equipos[ids[2 * n + 1]][0],
            "goles_local": None, "goles_visitante": None,
        })
    return proximos, historiales
