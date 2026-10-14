# TIPSTER

Pronósticos de la próxima jornada de la Champions League, publicados en una web pixel art:
https://gafasgithub.github.io/tipster (repositorio: https://github.com/gafasgithub/tipster).

## Cómo funciona

- `tipster_agentes.py` es la versión que se publica. Ejecuta 5 scripts de Python en cadena
  (`agentes/`): calendario (Wikipedia) → ligas (CSV de football-data.co.uk) → traductor (une
  nombres de equipos) → analista (modelo de Poisson ajustado por nivel de liga) → web.
  No usan IA ni claves de API. El usuario los llama "agentes".
- Tenis (pestaña aparte en la misma web): tenis-calendario (cuadros de Wikipedia) → tenis-resultados
  (Excel de tennis-data.co.uk, leído sin librerías) → tenis-traductor → tenis-analista (Elo + modelo
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

- Sin fuente de liga para Ucrania, Eslovaquia, Chequia, Azerbaiyán... (solo cuentan sus partidos de Champions).
- Corners, tarjetas, tiros y faltas solo existen en las ligas "principales" de football-data.co.uk.
- Saques de banda: ninguna fuente libre los tiene; se decidió no inventarlos.
- Tenis: tennis-data.co.uk va con unos días de retraso; el Elo acierta al favorito ~65% de las veces.
  Wikipedia no da la hora de los partidos de tenis. Los enlaces de tennis-data.co.uk se leen de su
  página alldata.php porque la carpeta de descarga tiene un nombre que puede cambiar.
- Los niveles de liga (`NIVEL_LIGA` en `agentes/analista.py`) están fijados a mano.

## Pendiente

- Panel para monitorizar en vivo lo que hacen los agentes (a partir de `estado/`).
