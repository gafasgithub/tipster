"""Agente Traductor: une los nombres de Wikipedia con los de football-data.co.uk."""
import difflib
import re
import unicodedata

from .base import Agente

# Nombre en Wikipedia -> nombre en football-data.co.uk, para los casos que no se deducen solos
ALIAS = {
    "Paris Saint-Germain": "Paris SG", "Manchester City": "Man City", "Manchester United": "Man United",
    "Atlético Madrid": "Ath Madrid", "Athletic Bilbao": "Ath Bilbao", "Real Betis": "Betis",
    "Real Sociedad": "Sociedad", "Espanyol": "Espanol", "Rayo Vallecano": "Vallecano",
    "Eintracht Frankfurt": "Ein Frankfurt", "Borussia Mönchengladbach": "M'gladbach",
    "Inter Milan": "Inter", "Sporting CP": "Sp Lisbon", "Braga": "Sp Braga",
    "Vitória de Guimarães": "Guimaraes", "Olympiacos": "Olympiakos", "AEK Athens": "AEK",
    "Union Saint-Gilloise": "St. Gilloise", "Nottingham Forest": "Nott'm Forest",
    "Red Bull Salzburg": "Salzburg", "Rapid Wien": "SK Rapid", "Austria Wien": "Austria Vienna",
    "Olympique de Marseille": "Marseille", "Olympique Lyonnais": "Lyon",
    "İstanbul Başakşehir": "Buyuksehyr", "Göztepe": "Goztep", "NEC": "Nijmegen",
}
PALABRAS_VACIAS = {
    "fc", "cf", "sk", "sc", "ac", "as", "afc", "club", "de", "fk", "kv", "ss", "calcio",
    "football", "sv", "bk", "if", "cp", "ssc", "rc", "ogc", "1907", "1909",
}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = texto.replace("ø", "o").replace("ı", "i").replace("ß", "ss")
    palabras = [p for p in re.split(r"[^a-z0-9]+", texto) if p and p not in PALABRAS_VACIAS]
    return " ".join(palabras)


class AgenteTraductor(Agente):
    nombre = "traductor"

    def trabajar(self, equipos, ligas):
        mapa, sin_traducir = {}, []
        for equipo in equipos.values():
            liga = ligas.get(equipo["pais"])
            if not liga:
                mapa[equipo["id"]] = None
                continue
            encontrado, metodo = self._buscar(equipo, liga["equipos"])
            if encontrado:
                mapa[equipo["id"]] = {"pais": equipo["pais"], "nombre": encontrado, "metodo": metodo}
                self.info(f"{equipo['nombre']} → {encontrado} ({metodo})")
            else:
                mapa[equipo["id"]] = None
                sin_traducir.append(equipo["nombre"])
                self.aviso(f"No encuentro a {equipo['nombre']} en {liga['nombre']}")
        traducidos = sum(1 for v in mapa.values() if v)
        self.metricas = {"equipos": len(equipos), "traducidos": traducidos, "sin_traducir": sin_traducir}
        return mapa

    def _buscar(self, equipo, candidatos):
        for nombre in (equipo["nombre"], equipo.get("wiki", "")):
            if ALIAS.get(nombre) in candidatos:
                return ALIAS[nombre], "alias"
        normalizados = {normalizar(c): c for c in candidatos}
        for nombre in (equipo["nombre"], equipo.get("wiki", "")):
            clave = normalizar(nombre)
            if clave in normalizados:
                return normalizados[clave], "exacto"
        clave = normalizar(equipo["nombre"])
        palabras = set(clave.split())
        for norm, original in normalizados.items():
            if palabras and (palabras <= set(norm.split()) or set(norm.split()) <= palabras):
                return original, "parecido"
        # Umbral alto: con 0.6, Torreense (segunda portuguesa) se confundía con Moreirense
        parecidos = difflib.get_close_matches(clave, list(normalizados), n=1, cutoff=0.8)
        if parecidos:
            return normalizados[parecidos[0]], "aproximado"
        return None, None
