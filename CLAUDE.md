# TIPSTER

Pronósticos de la próxima jornada de la Champions League, publicados en una web pixel art:
https://gafasgithub.github.io/tipster (repositorio: https://github.com/gafasgithub/tipster).

## Cómo funciona

- `tipster_agentes.py` es la versión que se publica. Ejecuta 5 scripts de Python en cadena
  (`agentes/`): calendario (Wikipedia) → ligas (CSV de football-data.co.uk) → traductor (une
  nombres de equipos) → analista (modelo de Poisson ajustado por nivel de liga) → web.
  No usan IA ni claves de API. El usuario los llama "agentes".
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
- Los niveles de liga (`NIVEL_LIGA` en `agentes/analista.py`) están fijados a mano.

## Pendiente

- Panel para monitorizar en vivo lo que hacen los agentes (a partir de `estado/`).
