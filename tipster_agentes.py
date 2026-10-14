"""TIPSTER con agentes: pronósticos de la Champions sin clave de API.

Cinco agentes trabajan en cadena:
  1. calendario  lee en Wikipedia la próxima jornada y los resultados de la Champions
  2. ligas       descarga de football-data.co.uk los partidos de liga de cada país
  3. traductor   une los nombres de los equipos entre ambas fuentes
  4. analista    calcula las probabilidades de goles, corners y tarjetas
  5. web         genera la página en web_agentes/index.html

Uso:
    py tipster_agentes.py            ejecuta los agentes
    py tipster_agentes.py --abrir    además abre la web en el navegador

Lo que hace cada agente queda en estado/ejecucion.json y estado/eventos.jsonl.
"""
import argparse
import sys
import webbrowser

from agentes.analista import AgenteAnalista
from agentes.base import Monitor
from agentes.calendario import AgenteCalendario
from agentes.ligas import AgenteLigas
from agentes.traductor import AgenteTraductor
from agentes.web import AgenteWeb

AGENTES = ["calendario", "ligas", "traductor", "analista", "web"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Pronósticos de la Champions con agentes")
    parser.add_argument("--abrir", action="store_true", help="abrir la web al terminar")
    args = parser.parse_args()

    monitor = Monitor(AGENTES)
    try:
        calendario = AgenteCalendario(monitor).ejecutar()
        equipos = {}
        for p in calendario["proximos"]:
            for lado in ("local", "visitante"):
                equipos[p[lado]["id"]] = p[lado]
        ligas = AgenteLigas(monitor).ejecutar({e["pais"] for e in equipos.values()})
        mapa = AgenteTraductor(monitor).ejecutar(equipos, ligas)
        analisis = AgenteAnalista(monitor).ejecutar(calendario, ligas, mapa)
        ruta = AgenteWeb(monitor).ejecutar(analisis)
    except Exception:
        monitor.terminar(ok=False)
        sys.exit("\nLa ejecución se detuvo por un error. Detalles en estado/eventos.jsonl")
    monitor.terminar(ok=True)
    print(f"\nListo. Web: {ruta}")
    if args.abrir:
        webbrowser.open(ruta.as_uri())


if __name__ == "__main__":
    main()
