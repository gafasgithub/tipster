"""Genera la página web con los resultados del análisis."""
import json
from pathlib import Path

PLANTILLA = Path(__file__).resolve().parent.parent / "plantilla.html"


def _json(datos):
    return json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")


def generar(analisis, destino, demo=False, tenis=None, europa=None):
    """analisis: datos de la Champions (o None si no hay); tenis y europa: opcionales."""
    futbol = {**analisis, "demo": demo} if analisis else None
    html = (PLANTILLA.read_text(encoding="utf-8")
            .replace("/*__DATOS__*/null", _json(futbol))
            .replace("/*__TENIS__*/null", _json(tenis))
            .replace("/*__EUROPA__*/null", _json(europa)))
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
