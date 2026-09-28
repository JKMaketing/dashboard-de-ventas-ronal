#!/usr/bin/env python3
"""
Fetches sales data from Google Sheet and updates const GIDS={...} and
const RAW=[...] in index.html.
Run: python update_data.py

Row format: [iso, asesor, sede, origen, venta(0/1), producto,
             total venta (col N), saldo pagado (col O), saldo por cobrar (col P)]
CARTAGO se excluye del dashboard.
"""
import csv, io, json, re, sys
from urllib.request import urlopen
from datetime import date

SHEET_ID = '1HRqhDS_63PWVutrRCHbEVEFtk0-n_r86ErlBMpAc0KE'
MESES = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO',
         'JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE']
EXCLUIR_SEDES = {'CARTAGO'}

def get(url):
    with urlopen(url, timeout=30) as r:
        return r.read().decode('utf-8')

def month_gids():
    # export?format=csv ignora el nombre de pestaña, así que necesitamos el gid.
    # htmlview lista cada pestaña como {name: "X", pageUrl: "...gid=N"}.
    html = get(f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview')
    gids = {}
    for name, gid in re.findall(r'\{name: "([^"]+)", pageUrl: "[^"]*?gid=(\d+)', html):
        if name.strip().upper() in MESES:
            gids[name.strip().upper()] = gid
    return gids

def fetch_tab(gid):
    # SIEMPRE export (no gviz): gviz vacía celdas cuyo tipo no coincide,
    # p. ej. una fecha mal escrita como "23//9/26".
    return get(f'https://docs.google.com/spreadsheets/d/{SHEET_ID}'
               f'/export?format=csv&gid={gid}')

def to_iso(s):
    # Tolera errores de digitación: "23//9/26", "27/8/26", "01/09/2026"
    m = re.match(r'(\d{1,2})/+(\d{1,2})/+(\d{2,4})', s.strip())
    if not m: return None
    y = m.group(3)
    if len(y) == 2: y = '20' + y
    if int(y) < 2000: y = str(date.today().year)  # p. ej. "23/08/0202"
    return f'{y}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}'

def norm_sede(s):
    s = (s or '').strip().upper()
    if s.startswith('JAMUND'): return 'JAMUNDÍ'
    if s.startswith('CERRITO'): return 'CERRITOS'
    return s

def money(s):
    s = str(s)
    cleaned = re.sub(r'[^0-9]', '', s)
    v = int(cleaned) if cleaned else 0
    return -v if '-' in s else v

gids = month_gids()
if not gids:
    print('ERROR: no month tabs found in htmlview — aborting', file=sys.stderr)
    sys.exit(1)

all_rows = []
for mes, gid in sorted(gids.items(), key=lambda kv: MESES.index(kv[0])):
    try:
        rows = list(csv.reader(io.StringIO(fetch_tab(gid))))
        n = 0
        for row in rows[1:]:
            if len(row) < 16:
                continue
            iso = to_iso(row[0])
            if not iso:
                continue
            sede = norm_sede(row[2])
            if sede in EXCLUIR_SEDES:
                continue
            venta = 1 if str(row[4]).strip().upper() == 'SI' else 0
            all_rows.append([iso, row[1].strip().upper(), sede, row[3].strip().upper(),
                             venta, row[6].strip().upper(),
                             money(row[13]), money(row[14]), money(row[15])])
            n += 1
        print(f'  {mes} (gid {gid}): {n} rows')
    except Exception as e:
        print(f'  {mes}: error — {e}')

all_rows.sort(key=lambda r: r[0])

if not all_rows:
    print('ERROR: no rows fetched — aborting', file=sys.stderr)
    sys.exit(1)

def bundled(obj):
    # The HTML file stores JS inside a JSON-encoded string, so:
    # - use literal \n (2 chars) as line separator, not actual newlines
    # - escape " as \" (2 chars), not literal double-quotes
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('"', '\\"')

raw_str = 'const RAW=[\\n' + ',\\n'.join(bundled(r) for r in all_rows) + '\\n];'
gids_str = 'const GIDS=' + bundled(gids) + ';'

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('const RAW=[')
if start == -1:
    print('ERROR: const RAW=[ not found in index.html', file=sys.stderr)
    sys.exit(1)
end = content.find('];', start) + 2
content = content[:start] + raw_str + content[end:]

gs = content.find('const GIDS=')
if gs == -1:
    print('ERROR: const GIDS= not found in index.html', file=sys.stderr)
    sys.exit(1)
ge = content.find(';', gs) + 1
content = content[:gs] + gids_str + content[ge:]

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Done: {len(all_rows)} rows, last date {all_rows[-1][0]}, tabs {gids}')
