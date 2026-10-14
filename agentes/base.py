"""Pieza común de los agentes: registro de actividad y descargas con caché.

Todo lo que hace cada agente queda en estado/:
  ejecucion.json  estado actual de cada agente (esperando, trabajando, ok, error) y sus métricas
  eventos.jsonl   una línea por cada cosa que hace un agente
"""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_ESTADO = RAIZ / "estado"
CARPETA_CACHE = RAIZ / ".cache" / "agentes"
AGENTE_HTTP = "TIPSTER/0.2 (proyecto personal; https://github.com/gafasgithub/tipster)"
API_WIKIPEDIA = "https://en.wikipedia.org/w/api.php"
MARCAS = {"info": " ", "aviso": "!", "error": "X"}


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Monitor:
    def __init__(self, nombres):
        CARPETA_ESTADO.mkdir(exist_ok=True)
        self.eventos = CARPETA_ESTADO / "eventos.jsonl"
        self.eventos.write_text("", encoding="utf-8")
        self.estado = {
            "inicio": ahora(), "fin": None, "ok": None,
            "agentes": {n: {"estado": "esperando"} for n in nombres},
        }
        self._guardar()

    def _guardar(self):
        temporal = CARPETA_ESTADO / "ejecucion.json.tmp"
        temporal.write_text(json.dumps(self.estado, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(CARPETA_ESTADO / "ejecucion.json")

    def evento(self, agente, nivel, mensaje):
        linea = {"ts": ahora(), "agente": agente, "nivel": nivel, "mensaje": mensaje}
        with self.eventos.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        print(f"[{agente:<10}] {MARCAS[nivel]} {mensaje}", flush=True)

    def actualizar(self, agente, **campos):
        self.estado["agentes"][agente].update(campos)
        self._guardar()

    def terminar(self, ok):
        self.estado.update(fin=ahora(), ok=ok)
        self._guardar()


class Agente:
    nombre = "agente"

    def __init__(self, monitor):
        self.monitor = monitor
        self.metricas = {}

    def info(self, mensaje):
        self.monitor.evento(self.nombre, "info", mensaje)

    def aviso(self, mensaje):
        self.monitor.evento(self.nombre, "aviso", mensaje)

    def ejecutar(self, *args):
        self.monitor.actualizar(self.nombre, estado="trabajando", inicio=ahora())
        t0 = time.time()
        try:
            resultado = self.trabajar(*args)
        except Exception as e:
            self.monitor.evento(self.nombre, "error", f"{type(e).__name__}: {e}")
            self.monitor.actualizar(self.nombre, estado="error", fin=ahora(), mensaje=str(e))
            raise
        self.monitor.actualizar(
            self.nombre, estado="ok", fin=ahora(),
            segundos=round(time.time() - t0, 1), metricas=self.metricas,
        )
        return resultado

    def trabajar(self, *args):
        raise NotImplementedError

    def descargar(self, url, horas_cache=6):
        """Devuelve el contenido de la URL, o None si no existe (404)."""
        CARPETA_CACHE.mkdir(parents=True, exist_ok=True)
        archivo = CARPETA_CACHE / hashlib.sha1(url.encode()).hexdigest()[:16]
        if archivo.exists() and time.time() - archivo.stat().st_mtime < horas_cache * 3600:
            return archivo.read_bytes()

        self.info(f"Descargando {url}")
        peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE_HTTP})
        for intento in range(1, 4):
            try:
                with urllib.request.urlopen(peticion, timeout=40) as respuesta:
                    datos = respuesta.read()
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                error = f"error {e.code}"
            except urllib.error.URLError as e:
                error = str(e.reason)
            if intento == 3:
                raise RuntimeError(f"No se pudo descargar {url} ({error})")
            self.aviso(f"Fallo al descargar ({error}), reintento {intento}/2 en 5 s")
            time.sleep(5)
        archivo.write_bytes(datos)
        time.sleep(1)  # pausa de cortesía con las webs
        return datos

    def wikitexto(self, pagina, horas_cache=1):
        """Texto fuente de una página de Wikipedia en inglés, o None si no existe."""
        parametros = urllib.parse.urlencode({
            "action": "parse", "page": pagina, "prop": "wikitext",
            "format": "json", "formatversion": 2, "redirects": 1,
        })
        datos = json.loads(self.descargar(f"{API_WIKIPEDIA}?{parametros}", horas_cache))
        return None if "error" in datos else datos["parse"]["wikitext"]
