"""Gera data/avenidas.js (carregado por index.html) a partir de data.json.

Passos para regenerar os dados:
  1. Consulta Overpass (q.overpass) -> osm.json
  2. Malhas do IBGE (municípios e UFs) e lista de municípios -> mun.geojson, uf.geojson, municipios.json
  3. python process.py -> data.json
  4. python build.py <pasta-com-data.json>
"""
import sys, pathlib
here = pathlib.Path(__file__).parent
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else here
out = here.parent / 'data' / 'avenidas.js'
out.parent.mkdir(exist_ok=True)
out.write_text('window.DATA = ' + (src / 'data.json').read_text(encoding='utf-8') + ';\n', encoding='utf-8')
print(out, out.stat().st_size)
