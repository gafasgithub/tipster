# TIPSTER

Pronósticos de la próxima jornada de la UEFA Champions League y de los torneos de tenis ATP/WTA
en juego, con una web estilo pixel art.

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
| `tenis-calendario` | Lee en Wikipedia los torneos ATP/WTA de la semana y los partidos pendientes de sus cuadros |
| `tenis-resultados` | Descarga de tennis-data.co.uk los resultados ATP y WTA de los últimos años |
| `tenis-traductor` | Une los nombres de los jugadores entre ambas fuentes |
| `tenis-analista` | Elo por jugador (general y por superficie) y simulación juego a juego: sets, juegos y tie-breaks |
| `web` | Genera `web_agentes/index.html` con las pestañas de fútbol y tenis |

Lo que hace cada agente queda en `estado/ejecucion.json` y `estado/eventos.jsonl`.

## Publicación automática

`.github/workflows/actualizar-web.yml` ejecuta los agentes cada día a las 8:00 (hora de España)
y publica la web en GitHub Pages.

Datos: [Wikipedia](https://en.wikipedia.org) (CC BY-SA), [football-data.co.uk](https://www.football-data.co.uk)
y [tennis-data.co.uk](http://www.tennis-data.co.uk).
