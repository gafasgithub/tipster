# TIPSTER

Pronósticos de la próxima jornada de la Champions League y la Europa League, y de tenis, publicados en una web pixel art:
https://gafasgithub.github.io/tipster (repositorio: https://github.com/gafasgithub/tipster).

## Cómo funciona

- `tipster_agentes.py` es la versión que se publica. Ejecuta 5 scripts de Python en cadena
  (`agentes/`): calendario (Wikipedia) → ligas (CSV de football-data.co.uk) → traductor (une
  nombres de equipos) → analista (modelo de Poisson ajustado por nivel de liga) → web.
  No usan IA ni claves de API. El usuario los llama "agentes".
- Cada competición de fútbol se añade en `COMPETICIONES` (`agentes/calendario.py`): el calendario lee
  todas, ligas y traductor trabajan con la unión de equipos y el analista analiza cada una con su propia
  media de goles. En la web (`plantilla.html`) hay pestañas FÚTBOL | TENIS y, dentro de
  fútbol, subpestañas CHAMPIONS | EUROPA LEAGUE; la Champions va en `DATOS` y la Europa League en `EUROPA`.
- Tenis (pestaña aparte en la misma web): tenis-calendario (cuadros de Wikipedia) → tenis-resultados
  (cuadros de Wikipedia de esta temporada y la anterior) → tenis-traductor → tenis-analista (Elo + modelo
  juego a juego en `agentes/tenis_modelo.py`, calibrado cada día con el % real de tie-breaks y la media
  real de juegos). Si un deporte falla, la web se publica con el otro.
- `tipster.py` + `src/` es la versión original con la API de football-data.org (clave en `.env`).
  Ya no se publica, pero `src/modelo.py` y `src/web.py` los reutilizan los agentes.
- `plantilla.html` es la web (sirve para ambas versiones). La letra pixelada no tiene tildes en
  mayúsculas: los textos en esa letra van sin tilde.
- `.github/workflows/actualizar-web.yml` publica en GitHub Pages cada día a las 8:00 (hora de
  España) y en cada push a `main`.
- Cada ejecución deja el registro de los agentes en `estado/ejecucion.json` y `estado/eventos.jsonl`.

## Probar cambios

- `py tipster_agentes.py --abrir` (en Windows se usa `py`, no `python`).
- Para ver la web sin abrir ventanas: captura con Edge en modo headless. Para el ancho de móvil,
  usar un iframe de 400 px (Edge headless no baja de unos 500 px de ventana).

## Limitaciones conocidas

- Sin fuente de liga para Ucrania, Eslovaquia, Chequia, Azerbaiyán, Croacia, Hungría, Israel, Chipre... (solo
  cuentan sus partidos europeos). Tampoco para equipos de segunda división (p. ej. Torreense): se les supone
  el nivel de la primera de su país.
- Corners, tarjetas, tiros y faltas solo existen en las ligas "principales" de football-data.co.uk.
- Saques de banda: ninguna fuente libre los tiene; se decidió no inventarlos.
- Tenis: tennis-data.co.uk se descartó porque bloquea (403) las descargas desde GitHub; no intentar
  saltarse ese bloqueo. Wikipedia no da la hora de los partidos ni el ranking ATP/WTA, y las fechas
  de los resultados son aproximadas (inicio del torneo + ronda).
- La caché `.cache/agentes` se conserva entre ejecuciones de GitHub con actions/cache; la frescura de
  cada página se mide con su archivo `.hora`, no con la fecha del archivo.
- Los niveles de liga (`NIVEL_LIGA` en `agentes/analista.py`) están fijados a mano.

## Pendiente

- Panel para monitorizar en vivo lo que hacen los agentes (a partir de `estado/`).
