"""Agente Web: genera la página con el análisis de fútbol y de tenis."""
from src import web

from .base import RAIZ, Agente

SALIDA = RAIZ / "web_agentes" / "index.html"
FUENTES_FUTBOL = [
    {"nombre": "Wikipedia (calendario y resultados de la Champions, licencia CC BY-SA)", "url": "https://en.wikipedia.org"},
    {"nombre": "football-data.co.uk (resultados y estadísticas de ligas)", "url": "https://www.football-data.co.uk"},
]
FUENTES_TENIS = [
    {"nombre": "Wikipedia (torneos y cuadros, licencia CC BY-SA)", "url": "https://en.wikipedia.org"},
    {"nombre": "tennis-data.co.uk (resultados ATP y WTA)", "url": "http://www.tennis-data.co.uk"},
]


class AgenteWeb(Agente):
    nombre = "web"

    def trabajar(self, futbol, tenis):
        ruta = web.generar(
            {**futbol, "fuentes": FUENTES_FUTBOL} if futbol else None, SALIDA,
            tenis={**tenis, "fuentes": FUENTES_TENIS} if tenis else None,
        )
        self.metricas = {
            "partidos_futbol": len(futbol["partidos"]) if futbol else None,
            "partidos_tenis": len(tenis["partidos"]) if tenis else None,
            "archivo": str(ruta),
        }
        self.info(f"Web generada en {ruta}")
        return ruta
