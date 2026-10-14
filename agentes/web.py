"""Agente Web: genera la página con el análisis."""
from src import web

from .base import RAIZ, Agente

SALIDA = RAIZ / "web_agentes" / "index.html"
FUENTES = [
    {"nombre": "Wikipedia (calendario y resultados de la Champions, licencia CC BY-SA)", "url": "https://en.wikipedia.org"},
    {"nombre": "football-data.co.uk (resultados y estadísticas de ligas)", "url": "https://www.football-data.co.uk"},
]


class AgenteWeb(Agente):
    nombre = "web"

    def trabajar(self, analisis):
        ruta = web.generar({**analisis, "fuentes": FUENTES}, SALIDA)
        self.metricas = {"partidos": len(analisis["partidos"]), "archivo": str(ruta)}
        self.info(f"Web generada en {ruta}")
        return ruta
