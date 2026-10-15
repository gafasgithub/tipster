"""Agente Web: genera la página con el análisis de fútbol y de tenis."""
from src import web

from .base import RAIZ, Agente

SALIDA = RAIZ / "web_agentes" / "index.html"
FUENTES_FUTBOL = [
    {"nombre": "Wikipedia (calendario y resultados de la Champions y la Europa League, licencia CC BY-SA)", "url": "https://en.wikipedia.org"},
    {"nombre": "football-data.co.uk (resultados y estadísticas de ligas)", "url": "https://www.football-data.co.uk"},
]
FUENTES_TENIS = [
    {"nombre": "Wikipedia (torneos, cuadros y resultados ATP y WTA, licencia CC BY-SA)", "url": "https://en.wikipedia.org"},
]


class AgenteWeb(Agente):
    nombre = "web"

    def trabajar(self, futbol, tenis):
        """futbol: análisis de cada competición ({"champions": ..., "europa": ...}), o {} si falló."""
        champions, europa = futbol.get("champions"), futbol.get("europa")
        ruta = web.generar(
            {**champions, "fuentes": FUENTES_FUTBOL} if champions else None, SALIDA,
            tenis={**tenis, "fuentes": FUENTES_TENIS} if tenis else None,
            europa={**europa, "fuentes": FUENTES_FUTBOL} if europa else None,
        )
        self.metricas = {
            "partidos_champions": len(champions["partidos"]) if champions else None,
            "partidos_europa": len(europa["partidos"]) if europa else None,
            "partidos_tenis": len(tenis["partidos"]) if tenis else None,
            "archivo": str(ruta),
        }
        self.info(f"Web generada en {ruta}")
        return ruta
