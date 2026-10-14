# TIPSTER

Pronósticos de la próxima jornada de la UEFA Champions League, con una web estilo pixel art.

Para cada partido estima, con un modelo de Poisson basado en los últimos partidos de cada equipo:
victoria local / empate / victoria visitante, más de 2.5 goles, ambos marcan, marcador más probable y cuota justa.

Son probabilidades, no certezas. Si apuestas, hazlo con responsabilidad.

## Uso local

Requiere Python 3.10 o superior (sin librerías extra).

```
py tipster.py --demo --abrir   # datos de ejemplo, sin clave
py tipster.py --abrir          # datos reales
```

Para los datos reales, copia `.env.example` como `.env` y pon tu clave gratuita de
[football-data.org](https://www.football-data.org/client/register).

## Publicación automática

`.github/workflows/actualizar-web.yml` regenera la web cada día a las 8:00 (hora de España)
y la publica en GitHub Pages. La clave se guarda como secreto `FOOTBALL_DATA_API_KEY` del repositorio.

Datos proporcionados por [football-data.org](https://www.football-data.org).
