"""Cliente mínimo para la API de football-data.org (v4)."""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL_BASE = "https://api.football-data.org/v4"
PAUSA_SEGUNDOS = 6.5  # el plan gratuito permite 10 peticiones por minuto
HORAS_CACHE = 6
ESTADOS_PENDIENTES = {"SCHEDULED", "TIMED", "IN_PLAY", "PAUSED"}


class ErrorAPI(Exception):
    pass


class ClienteAPI:
    def __init__(self, token, carpeta_cache):
        self.token = token
        self.cache = Path(carpeta_cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._ultima_peticion = 0.0

    def _get(self, ruta, **params):
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{URL_BASE}{ruta}" + (f"?{query}" if query else "")
        archivo = self.cache / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
        if archivo.exists() and time.time() - archivo.stat().st_mtime < HORAS_CACHE * 3600:
            return json.loads(archivo.read_text(encoding="utf-8"))

        for _ in range(3):
            espera = PAUSA_SEGUNDOS - (time.time() - self._ultima_peticion)
            if espera > 0:
                time.sleep(espera)
            self._ultima_peticion = time.time()
            peticion = urllib.request.Request(url, headers={"X-Auth-Token": self.token})
            try:
                with urllib.request.urlopen(peticion, timeout=30) as respuesta:
                    datos = json.loads(respuesta.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    print("  Límite de peticiones alcanzado, esperando 60 s...")
                    time.sleep(60)
                    continue
                cuerpo = e.read().decode("utf-8", "replace")
                try:
                    mensaje = json.loads(cuerpo).get("message", cuerpo)
                except ValueError:
                    mensaje = cuerpo
                raise ErrorAPI(f"Error {e.code} en {ruta}: {mensaje[:300]}")
            except urllib.error.URLError as e:
                raise ErrorAPI(f"No se pudo conectar con football-data.org: {e.reason}")
            archivo.write_text(json.dumps(datos), encoding="utf-8")
            return datos
        raise ErrorAPI(f"Demasiados intentos fallidos en {ruta}")

    def partidos_champions(self):
        """Todos los partidos de la Champions de la temporada actual."""
        datos = self._get("/competitions/CL/matches")
        return [_normalizar(p) for p in datos.get("matches", [])]

    def historial_equipo(self, equipo_id, dias=150, limite=10):
        """Últimos partidos terminados del equipo (todas las competiciones disponibles)."""
        hoy = datetime.now(timezone.utc).date()
        datos = self._get(
            f"/teams/{equipo_id}/matches",
            status="FINISHED",
            dateFrom=(hoy - timedelta(days=dias)).isoformat(),
            dateTo=hoy.isoformat(),
        )
        partidos = [_normalizar(p) for p in datos.get("matches", [])]
        partidos = [p for p in partidos if p["goles_local"] is not None]
        partidos.sort(key=lambda p: p["fecha"])
        return partidos[-limite:]


def siguiente_jornada(partidos, ventana_dias=3):
    """Partidos pendientes de la próxima jornada (misma fase y número de jornada)."""
    pendientes = [
        p for p in partidos
        if p["estado"] in ESTADOS_PENDIENTES and p["local"]["id"] and p["visitante"]["id"]
    ]
    if not pendientes:
        return []
    pendientes.sort(key=lambda p: p["fecha"])
    primero = pendientes[0]
    if primero["jornada"] is not None:
        return [
            p for p in pendientes
            if p["etapa"] == primero["etapa"] and p["jornada"] == primero["jornada"]
        ]
    limite = _fecha(primero["fecha"]) + timedelta(days=ventana_dias)
    return [p for p in pendientes if _fecha(p["fecha"]) <= limite]


def partidos_terminados_de(equipo_id, partidos, limite=10):
    """Alternativa si falla el historial: partidos de Champions ya jugados por el equipo."""
    propios = [
        p for p in partidos
        if p["goles_local"] is not None and equipo_id in (p["local"]["id"], p["visitante"]["id"])
    ]
    propios.sort(key=lambda p: p["fecha"])
    return propios[-limite:]


def _fecha(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def _equipo(e):
    e = e or {}
    nombre = e.get("name") or "Por definir"
    return {
        "id": e.get("id"),
        "nombre": nombre,
        "corto": e.get("shortName") or e.get("tla") or nombre,
        "tla": e.get("tla") or "",
        "escudo": e.get("crest") or "",
    }


def _normalizar(p):
    marcador = (p.get("score") or {}).get("fullTime") or {}
    return {
        "id": p["id"],
        "fecha": p["utcDate"],
        "estado": p.get("status"),
        "etapa": p.get("stage"),
        "jornada": p.get("matchday"),
        "competicion": (p.get("competition") or {}).get("name", ""),
        "local": _equipo(p.get("homeTeam")),
        "visitante": _equipo(p.get("awayTeam")),
        "goles_local": marcador.get("home"),
        "goles_visitante": marcador.get("away"),
    }
