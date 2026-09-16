#!/usr/bin/env python3
"""
Fetches sales data from Google Sheet and updates const RAW=[...] in index.html.
Run: python update_data.py
"""
import csv, io, json, re, sys
from urllib.request import urlopen
from datetime import date

SHEET_ID = '1HRqhDS_63PWVutrRCHbEVEFtk0-n_r86ErlBMpAc0KE'
MESES = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO',
         'JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE']

def fetch_tab(month):
    url = (f'https://docs.google.com/spreadsheets/d/{SHEET_ID}'
           f'/gviz/tq?tqx=out:csv&sheet={month}')
    with urlopen(url, timeout=15) as r:
        return r.read().decode('utf-8')

def to_iso(s):
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', s.strip())
    if not m: return None
    return f'{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}'

def norm_sede(s):
    s = (s or '').strip().upper()
    if s.startswith('JAMUND'): return 'JAMUNDÍ'
    if s.startswith('CERRITO'): return 'CERRITOS'
    return s

def money(s):
    cleaned = re.sub(r'[^0-9]', '', str(s))
    return int(cleaned) if cleaned else 0

all_rows = []
seen = set()

for mes in MESES:
    try:
        text = fetch_tab(mes)
        if text in seen:
            continue
        seen.add(text)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        # Skip header rows — find first row where col[0] looks like DD/MM/YYYY
        data_start = None
        for i, row in enumerate(rows):
            if row and re.match(r'\d{1,2}/\d{1,2}/\d{4}', row[0].strip()):
                data_start = i
                break
        if data_start is None:
            continue
        for row in rows[data_start:]:
            if len(row) < 6:
                continue
            iso = to_iso(row[0])
            if not iso:
                continue
            venta = 1 if str(row[4]).strip().upper() == 'SI' else 0
            total  = money(row[13]) if len(row) > 13 else 0
            pagado = money(row[14]) if len(row) > 14 else 0
            all_rows.append([iso, row[1].strip(), norm_sede(row[2]),
                             row[3].strip(), venta, row[6].strip(), total, pagado])
        print(f'  {mes}: {len(rows) - data_start} rows')
    except Exception as e:
        print(f'  {mes}: error — {e}')

all_rows.sort(key=lambda r: r[0])

if not all_rows:
    print('ERROR: no rows fetched — aborting', file=sys.stderr)
    sys.exit(1)

raw_str = 'const RAW=[\n' + ',\n'.join(
    json.dumps(r, ensure_ascii=False) for r in all_rows
) + '\n];'

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('const RAW=[')
end   = content.find('];', start) + 2
if start == -1:
    print('ERROR: const RAW=[ not found in index.html', file=sys.stderr)
    sys.exit(1)

new_content = content[:start] + raw_str + content[end:]

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

last = all_rows[-1][0]
print(f'Done: {len(all_rows)} rows, last date {last}')
