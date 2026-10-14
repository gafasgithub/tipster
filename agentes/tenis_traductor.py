"""Agente Tenis-Traductor: une los nombres de Wikipedia ("Alex de Minaur")
con los de tennis-data.co.uk ("De Minaur A.")."""
import difflib
import re
import unicodedata
from collections import Counter, defaultdict

from .base import Agente


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = texto.replace("ø", "o").replace("ł", "l").replace("đ", "d").replace("ß", "ss")
    return " ".join(re.split(r"[^a-z0-9]+", texto)).strip()


def _clave(nombre_corto):
    """'De Minaur A.' -> ('de minaur', 'a')"""
    partes = nombre_corto.strip().rsplit(" ", 1)
    if len(partes) < 2:
        return normalizar(nombre_corto), ""
    return normalizar(partes[0]), normalizar(partes[1])[:1]


class AgenteTenisTraductor(Agente):
    nombre = "tenis-traductor"

    def trabajar(self, partidos, resultados):
        indices = {c: self._indice(lista) for c, lista in resultados.items()}
        mapa, sin_traducir = {}, []
        for partido in partidos:
            for jugador in partido["jugadores"]:
                clave = f"{partido['circuito']}|{jugador['nombre']}"
                if clave in mapa:
                    continue
                encontrado, metodo = self._buscar(jugador["nombre"], *indices[partido["circuito"]])
                mapa[clave] = encontrado
                if encontrado:
                    self.info(f"{jugador['nombre']} → {encontrado} ({metodo})")
                else:
                    sin_traducir.append(jugador["nombre"])
                    self.aviso(f"No encuentro resultados de {jugador['nombre']} ({partido['circuito']})")
        self.metricas = {"jugadores": len(mapa), "traducidos": sum(1 for v in mapa.values() if v),
                         "sin_traducir": sin_traducir}
        return mapa

    def _indice(self, partidos):
        frecuencia = Counter(n for p in partidos for n in (p["ganador"], p["perdedor"]))
        por_clave, por_apellido = defaultdict(list), defaultdict(list)
        for nombre in frecuencia:
            apellido, inicial = _clave(nombre)
            por_clave[(apellido, inicial)].append(nombre)
            por_apellido[apellido].append(nombre)
        return por_clave, por_apellido, frecuencia

    def _buscar(self, nombre, por_clave, por_apellido, frecuencia):
        palabras = normalizar(nombre).split()
        if len(palabras) < 2:
            return None, None
        candidatas = [(" ".join(palabras[i:]), palabras[0][0]) for i in range(1, len(palabras))]
        candidatas.append((palabras[0], palabras[1][0]))  # nombres asiáticos: apellido primero
        for clave in candidatas:
            if clave in por_clave:
                return max(por_clave[clave], key=frecuencia.get), "exacto"
        for i in range(1, len(palabras)):
            apellido = " ".join(palabras[i:])
            if len(por_apellido.get(apellido, [])) == 1:
                return por_apellido[apellido][0], "apellido"
        parecidos = difflib.get_close_matches(" ".join(palabras[1:]), list(por_apellido), n=1, cutoff=0.85)
        if parecidos and len(por_apellido[parecidos[0]]) == 1:
            return por_apellido[parecidos[0]][0], "aproximado"
        return None, None
