"""Agente Tenis-Resultados: lee en Wikipedia los cuadros de todos los torneos ATP y WTA
de la temporada actual y la anterior, con el marcador de cada partido.

Las páginas de torneos ya terminados casi no cambian, así que se guardan durante semanas;
las de torneos en curso se vuelven a leer cada hora.
"""
from datetime import datetime, timedelta, timezone

from .base import Agente
from .tenis_calendario import partidos_jugados, torneos_del_calendario


class AgenteTenisResultados(Agente):
    nombre = "tenis-resultados"

    def trabajar(self):
        hoy = datetime.now(timezone.utc).date()
        partidos, alias = {"ATP": [], "WTA": []}, {}
        for circuito in partidos:
            for anio in (hoy.year - 1, hoy.year):
                pagina = f"{anio} {circuito} Tour"
                texto = self.wikitexto(pagina, horas_cache=24 if anio == hoy.year else 24 * 30)
                if texto is None:
                    self.aviso(f"No existe la página «{pagina}»")
                    continue
                torneos = [t for t in torneos_del_calendario(texto, anio, circuito)
                           if t["cuadro"] and t["inicio"] <= hoy]
                antes = len(partidos[circuito])
                for torneo in torneos:
                    terminado = torneo["fin"] < hoy - timedelta(days=2)
                    cuadro = self.wikitexto(torneo["cuadro"], horas_cache=24 * 60 if terminado else 1)
                    if cuadro is None:
                        continue
                    for partido in partidos_jugados(cuadro, torneo):
                        alias.update(partido.pop("alias"))
                        partidos[circuito].append(partido)
                self.info(f"{circuito} {anio}: {len(torneos)} torneos, "
                          f"{len(partidos[circuito]) - antes} partidos terminados")

        for circuito, lista in partidos.items():
            lista.sort(key=lambda p: (p["fecha"], p["orden"]))
        if not any(partidos.values()):
            raise RuntimeError("No se pudo leer ningún resultado de tenis en Wikipedia")
        self.metricas = {c: len(l) for c, l in partidos.items()}
        return {"partidos": partidos, "alias": alias}
