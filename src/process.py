import json, math, collections
from shapely.geometry import shape, LineString, Point, Polygon, mapping
from shapely.strtree import STRtree
from shapely.ops import unary_union, linemerge, transform

osm = json.load(open('osm.json'))['elements']
mun = json.load(open('mun.geojson'))['features']
names = {m['id']: m for m in json.load(open('municipios.json'))}

polys = [shape(f['geometry']) for f in mun]
codes = [int(f['properties']['codarea']) for f in mun]
tree = STRtree(polys)

SKIP = {'footway','path','steps','proposed','cycleway'}
bycity = collections.defaultdict(list)
unassigned = 0
for e in osm:
    hw = e['tags'].get('highway')
    if hw in SKIP: continue
    coords = [(p['lon'], p['lat']) for p in e['geometry']]
    if len(coords) < 2: continue
    ls = LineString(coords)
    mid = ls.interpolate(0.5, normalized=True)
    idx = tree.query(mid, predicate='within')
    if len(idx) == 0:
        idx = [tree.nearest(mid)]; unassigned += 1
    bycity[codes[idx[0]]].append((e, ls))
print('ways assigned', sum(len(v) for v in bycity.values()), 'nearest-fallback', unassigned, 'cities', len(bycity))

def proj_for(lat0, lon0):
    k = math.cos(math.radians(lat0)); R = 6371008.8
    return lambda x, y, z=None: ((x - lon0) * math.pi/180 * R * k, (y - lat0) * math.pi/180 * R)

def enc_num(v):
    v = ~(v << 1) if v < 0 else (v << 1)
    out = ''
    while v >= 0x20:
        out += chr((0x20 | (v & 0x1f)) + 63); v >>= 5
    return out + chr(v + 63)
def encode(coords):  # coords (lon,lat) -> google polyline, 1e5
    out, plat, plon = '', 0, 0
    for lon, lat in coords:
        la, lo = round(lat*1e5), round(lon*1e5)
        out += enc_num(la - plat) + enc_num(lo - plon); plat, plon = la, lo
    return out

def poly_enc(p, tol=0.0015):
    p = p.simplify(tol)
    gs = p.geoms if p.geom_type=='MultiPolygon' else [p]
    return [encode(list(g.exterior.coords)) for g in gs if g.area > 1e-6]
RANK = ['motorway','trunk','primary','secondary','tertiary','unclassified','residential','living_street','service','track','pedestrian','busway','construction']
cities = []
for code, items in bycity.items():
    lines = [ls for _, ls in items]
    u = unary_union(lines)
    c = u.centroid
    f = proj_for(c.y, c.x)
    m = transform(f, u)
    r = 50.0
    bb = m.buffer(r, cap_style='flat', join_style='round')
    length = sum(max(Polygon(g.exterior).length/2 - 2*r, 0) for g in (bb.geoms if bb.geom_type=='MultiPolygon' else [bb]))
    length = min(length, m.length)
    raw = sum(transform(f, l).length for l in lines)
    # separate stretches: components more than 300 m apart
    comps = m.buffer(150).geoms if m.buffer(150).geom_type == 'MultiPolygon' else [m.buffer(150)]
    merged = linemerge(u) if u.geom_type != 'LineString' else u
    parts = list(merged.geoms) if hasattr(merged, 'geoms') else [merged]
    enc = [encode(list(p.simplify(0.00003).coords)) for p in parts]
    hws = collections.Counter()
    for e, ls in items:
        hws[e['tags'].get('highway')] += transform(f, ls).length
    top = max(hws, key=hws.get)
    info = names.get(code)
    if info:
        uf = info['microrregiao']['mesorregiao']['UF'] if info.get('microrregiao') else info['regiao-imediata']['regiao-intermediaria']['UF']
        nm, sg, reg = info['nome'], uf['sigla'], uf['regiao']['sigla']
    else:
        nm, sg, reg = str(code), '?', '?'
    minx, miny, maxx, maxy = u.bounds
    cities.append(dict(c=code, n=nm, uf=sg, r=reg, L=round(length), raw=round(raw), k=len(comps),
                       hw=top, ll=[round(c.y,5), round(c.x,5)], b=[round(miny,5), round(minx,5), round(maxy,5), round(maxx,5)],
                       g=enc, w=len(items), o=poly_enc(polys[codes.index(code)])))
cities.sort(key=lambda d: -d['L'])
json.dump(cities, open('cities.json','w'), ensure_ascii=False, separators=(',',':'))
print(len(cities), 'size', len(json.dumps(cities, ensure_ascii=False, separators=(',',':'))))
for d in cities[:15]: print(d['n'], d['uf'], d['L'], d['raw'], d['k'], d['hw'])
print('total km', sum(d['L'] for d in cities)/1000)
print(collections.Counter(d['uf'] for d in cities).most_common())
print('missing names', [d['c'] for d in cities if d['uf']=='?'])

ufs = json.load(open('uf.geojson'))['features']
uf_out = []
for f in ufs:
    p = shape(f['geometry'])
    uf_out.append(dict(c=int(f['properties']['codarea']), o=poly_enc(p, 0.01)))
json.dump(dict(cities=cities, ufs=uf_out, generated='2026-09-22'), open('data.json','w'), ensure_ascii=False, separators=(',',':'))
import os; print('data.json', os.path.getsize('data.json'))

# UF metadata: sigla, nome, total de municípios
ufmeta = {}
for m in json.load(open('municipios.json')):
    uf = m['microrregiao']['mesorregiao']['UF'] if m.get('microrregiao') else m['regiao-imediata']['regiao-intermediaria']['UF']
    d = ufmeta.setdefault(uf['id'], dict(s=uf['sigla'], n=uf['nome'], t=0))
    d['t'] += 1
for u in uf_out: u.update(ufmeta[u['c']])
json.dump(dict(cities=cities, ufs=uf_out, total=len(json.load(open('municipios.json'))), generated='2026-09-22'), open('data.json','w'), ensure_ascii=False, separators=(',',':'))
print('data.json', os.path.getsize('data.json'), [ (u['s'],u['t']) for u in uf_out][:5])
