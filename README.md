# TIPSTER

Pronósticos de la próxima jornada de la UEFA Champions League, con una web estilo pixel art.

Para cada partido estima, con un modelo de Poisson basado en los últimos partidos de cada equipo:
victoria local / empate / victoria visitante, más de 2.5 goles, ambos marcan, marcador más probable,
cuota justa, corners y tarjetas.

Son probabilidades, no certezas. Si apuestas, hazlo con responsabilidad.

## Uso local

Requiere Python 3.10 o superior (sin librerías extra).

```
py tipster_agentes.py --abrir   # versión con agentes, sin clave (la que se publica)
py tipster.py --demo --abrir    # versión original con datos de ejemplo
py tipster.py --abrir           # versión original con la API de football-data.org (requiere clave en .env)
```

## Los agentes

| Agente | Qué hace |
|---|---|
| `calendario` | Lee en Wikipedia la próxima jornada y los resultados de la Champions |
| `ligas` | Descarga de football-data.co.uk los partidos de liga de cada país (goles, xG, corners, tarjetas) |
| `traductor` | Une los nombres de los equipos entre ambas fuentes |
| `analista` | Calcula las probabilidades, ajustando por el nivel de cada liga |
| `web` | Genera `web_agentes/index.html` |

Lo que hace cada agente queda en `estado/ejecucion.json` y `estado/eventos.jsonl`.

## Publicación automática

`.github/workflows/actualizar-web.yml` ejecuta los agentes cada día a las 8:00 (hora de España)
y publica la web en GitHub Pages.

Datos: [Wikipedia](https://en.wikipedia.org) (CC BY-SA) y [football-data.co.uk](https://www.football-data.co.uk).
