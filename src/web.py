"""Genera la página web con los resultados del análisis."""
import json
from pathlib import Path

PLANTILLA = Path(__file__).resolve().parent.parent / "plantilla.html"


def _json(datos):
    return json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")


def generar(analisis, destino, demo=False, tenis=None):
    """analisis: datos de fútbol (o None si no hay); tenis: datos de tenis (opcional)."""
    futbol = {**analisis, "demo": demo} if analisis else None
    html = (PLANTILLA.read_text(encoding="utf-8")
            .replace("/*__DATOS__*/null", _json(futbol))
            .replace("/*__TENIS__*/null", _json(tenis)))
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
