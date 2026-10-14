"""TIPSTER: pronósticos de la próxima jornada de la Champions League.

Uso:
    py tipster.py             datos reales (requiere la clave en el archivo .env)
    py tipster.py --demo      datos de ejemplo, sin clave
    py tipster.py --abrir     además abre la web en el navegador
"""
import argparse
import os
import sys
import webbrowser
from pathlib import Path

from src import api, demo, modelo, web

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "web" / "index.html"


def cargar_env():
    archivo = RAIZ / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def datos_reales():
    token = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    if not token or token.startswith("pega-aqui"):
        sys.exit(
            "Falta la clave de football-data.org.\n"
            "  1. Copia el archivo .env.example y renómbralo a .env\n"
            "  2. Pega tu clave después de FOOTBALL_DATA_API_KEY=\n"
            "Mientras tanto puedes probar con:  py tipster.py --demo"
        )
    cliente = api.ClienteAPI(token, RAIZ / ".cache")
    print("Descargando partidos de la Champions League...")
    partidos_cl = cliente.partidos_champions()
    proximos = api.siguiente_jornada(partidos_cl)
    if not proximos:
        print("No hay partidos pendientes de Champions en este momento.")
        return [], {}

    equipos = {}
    for p in proximos:
        for lado in ("local", "visitante"):
            equipos[p[lado]["id"]] = p[lado]["corto"]
    print(f"{len(proximos)} partidos encontrados. Analizando {len(equipos)} equipos "
          f"(la primera vez tarda unos minutos por el límite de la API gratuita)...")

    historiales = {}
    for n, (equipo_id, nombre) in enumerate(equipos.items(), 1):
        print(f"  [{n}/{len(equipos)}] {nombre}")
        try:
            historiales[equipo_id] = cliente.historial_equipo(equipo_id)
        except api.ErrorAPI as e:
            print(f"    Aviso: {e}. Uso solo sus partidos de Champions.")
            historiales[equipo_id] = api.partidos_terminados_de(equipo_id, partidos_cl)
    return proximos, historiales


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Pronósticos de la jornada de Champions League")
    parser.add_argument("--demo", action="store_true", help="usar datos de ejemplo (sin clave)")
    parser.add_argument("--abrir", action="store_true", help="abrir la web al terminar")
    args = parser.parse_args()

    cargar_env()
    try:
        proximos, historiales = demo.generar() if args.demo else datos_reales()
    except api.ErrorAPI as e:
        sys.exit(f"Error: {e}")

    analisis = modelo.analizar_jornada(proximos, historiales)
    ruta = web.generar(analisis, SALIDA, demo=args.demo)
    print(f"\nListo: {len(analisis['partidos'])} partidos analizados.")
    print(f"Web generada en: {ruta}")
    if args.abrir:
        webbrowser.open(ruta.as_uri())


if __name__ == "__main__":
    main()
