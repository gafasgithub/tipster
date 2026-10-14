"""Genera la página web con los resultados del análisis."""
import json
from pathlib import Path

PLANTILLA = Path(__file__).resolve().parent.parent / "plantilla.html"


def generar(analisis, destino, demo=False):
    datos = json.dumps({**analisis, "demo": demo}, ensure_ascii=False).replace("</", "<\\/")
    html = PLANTILLA.read_text(encoding="utf-8").replace("/*__DATOS__*/null", datos)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
