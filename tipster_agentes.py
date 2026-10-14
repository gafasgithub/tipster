"""TIPSTER con agentes: pronósticos de fútbol (Champions) y tenis (ATP/WTA) sin clave de API.

Fútbol:
  1. calendario         lee en Wikipedia la próxima jornada y los resultados de la Champions
  2. ligas              descarga de football-data.co.uk los partidos de liga de cada país
  3. traductor          une los nombres de los equipos entre ambas fuentes
  4. analista           calcula las probabilidades de goles, corners, tarjetas, tiros y faltas
Tenis:
  5. tenis-calendario   busca en Wikipedia los torneos en juego y sus partidos pendientes
  6. tenis-resultados   descarga de tennis-data.co.uk los resultados ATP y WTA recientes
  7. tenis-traductor    une los nombres de los jugadores entre ambas fuentes
  8. tenis-analista     calcula un Elo por jugador y simula cada partido juego a juego
Y al final:
  9. web                genera la página en web_agentes/index.html

Si un deporte falla, la web se publica igualmente con el otro.

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
from agentes.tenis_analista import AgenteTenisAnalista
from agentes.tenis_calendario import AgenteTenisCalendario
from agentes.tenis_resultados import AgenteTenisResultados
from agentes.tenis_traductor import AgenteTenisTraductor
from agentes.traductor import AgenteTraductor
from agentes.web import AgenteWeb

AGENTES = ["calendario", "ligas", "traductor", "analista",
           "tenis-calendario", "tenis-resultados", "tenis-traductor", "tenis-analista", "web"]


def futbol(monitor):
    calendario = AgenteCalendario(monitor).ejecutar()
    equipos = {}
    for p in calendario["proximos"]:
        for lado in ("local", "visitante"):
            equipos[p[lado]["id"]] = p[lado]
    ligas = AgenteLigas(monitor).ejecutar({e["pais"] for e in equipos.values()})
    mapa = AgenteTraductor(monitor).ejecutar(equipos, ligas)
    return AgenteAnalista(monitor).ejecutar(calendario, ligas, mapa)


def tenis(monitor):
    calendario = AgenteTenisCalendario(monitor).ejecutar()
    resultados = AgenteTenisResultados(monitor).ejecutar()
    mapa = AgenteTenisTraductor(monitor).ejecutar(calendario["partidos"], resultados)
    return AgenteTenisAnalista(monitor).ejecutar(calendario, resultados, mapa)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Pronósticos de fútbol y tenis con agentes")
    parser.add_argument("--abrir", action="store_true", help="abrir la web al terminar")
    args = parser.parse_args()

    monitor = Monitor(AGENTES)
    resultados = {}
    for deporte, ejecutar in (("fútbol", futbol), ("tenis", tenis)):
        try:
            resultados[deporte] = ejecutar(monitor)
        except Exception:
            resultados[deporte] = None
            print(f"\n!! La parte de {deporte} falló; la web se generará sin ella.\n")
    if not any(resultados.values()):
        monitor.terminar(ok=False)
        sys.exit("\nLos dos deportes fallaron. Detalles en estado/eventos.jsonl")
    try:
        ruta = AgenteWeb(monitor).ejecutar(resultados["fútbol"], resultados["tenis"])
    except Exception:
        monitor.terminar(ok=False)
        sys.exit("\nNo se pudo generar la web. Detalles en estado/eventos.jsonl")
    monitor.terminar(ok=all(resultados.values()))
    print(f"\nListo. Web: {ruta}")
    if args.abrir:
        webbrowser.open(ruta.as_uri())


if __name__ == "__main__":
    main()
