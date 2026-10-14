"""Agente Tenis-Traductor: comprueba que cada jugador del calendario aparece en los resultados.

Las dos cosas vienen de Wikipedia, así que casi siempre el nombre coincide tal cual. Si no,
se prueba sin tildes ni guiones y, por último, con un parecido muy alto.
"""
import difflib
import re
import unicodedata

from .base import Agente


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = texto.replace("ø", "o").replace("ł", "l").replace("đ", "d").replace("ß", "ss")
    return " ".join(re.split(r"[^a-z0-9]+", texto)).strip()


class AgenteTenisTraductor(Agente):
    nombre = "tenis-traductor"

    def trabajar(self, partidos, resultados):
        indices = {}
        for circuito, lista in resultados["partidos"].items():
            nombres = {n for p in lista for n in (p["ganador"], p["perdedor"])}
            indices[circuito] = (nombres, {normalizar(n): n for n in nombres})
        mapa, sin_traducir, aproximados = {}, [], 0
        for partido in partidos:
            nombres, normalizados = indices[partido["circuito"]]
            for jugador in partido["jugadores"]:
                clave = f"{partido['circuito']}|{jugador['nombre']}"
                if clave in mapa:
                    continue
                nombre = jugador["nombre"]
                if nombre in nombres:
                    mapa[clave] = nombre
                    continue
                parecido = normalizados.get(normalizar(nombre)) or next(iter(
                    normalizados[n] for n in difflib.get_close_matches(normalizar(nombre), list(normalizados), n=1, cutoff=0.9)), None)
                mapa[clave] = parecido
                if parecido:
                    aproximados += 1
                    self.info(f"{nombre} → {parecido}")
                else:
                    sin_traducir.append(nombre)
                    self.aviso(f"No hay resultados de {nombre} ({partido['circuito']}) en las dos últimas temporadas")
        self.metricas = {"jugadores": len(mapa), "traducidos": sum(1 for v in mapa.values() if v),
                         "aproximados": aproximados, "sin_traducir": sin_traducir}
        return mapa
