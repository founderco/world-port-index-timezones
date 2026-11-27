# Makes a table of the time zone of each port in the NGA World Port Index, and a compact JSON
# list of the same ports for apps, from:
#   - the NGA World Port Index (US Government work, public domain): NGA's UpdatedPub150.csv from
#     https://msi.nga.mil/Publications/WPI, and for country codes the older shapefile edition on
#     HDX, https://data.humdata.org/dataset/world-port-index (WPI.dbf in world_port_index.zip);
#   - timezone-boundary-builder's timezones.geojson (ODbL, (c) OpenStreetMap contributors), from
#     https://github.com/evansiroky/timezone-boundary-builder/releases (unzip to combined.json).
#
#   python3 -I port-timezones.py UpdatedPub150.csv combined.json ports.json port-timezones.csv WPI.dbf
#
# The current CSV names countries in words. Their ISO codes come from the 2017 edition's WPI.dbf
# (optional last argument), by joining the two on the index number; failing that, from the first
# two letters of the port's UN/LOCODE.
#
# Display names in port-name-overrides.csv, next to this script, replace the index's (Singapore's
# cruise port is "Keppel - (East Singapore)" there); the index's name is kept as the alias.
#
# Each port's time zone is the boundary polygon it lies in; a port just offshore of every
# polygon takes the nearest one within 0.5 degrees, and is left out beyond that.
# With --test, checks the lookup on three known ports (Benoa, Phuket, Singapore) and exits.
import csv, json, math, struct, sys

def load_zones(path):
    zones = []
    for f in json.load(open(path))["features"]:
        tz = f["properties"]["tzid"]
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            xs = [p[0] for p in poly[0]]; ys = [p[1] for p in poly[0]]
            zones.append((tz, poly, (min(xs), min(ys), max(xs), max(ys))))
    return zones

def in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]; xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside

def in_poly(x, y, poly):
    return in_ring(x, y, poly[0]) and not any(in_ring(x, y, hole) for hole in poly[1:])

def segment_distance(x, y, a, b):
    # Degrees, with longitude scaled by cos(latitude); fine for "nearest within 0.5 degrees".
    k = math.cos(math.radians(y))
    ax, ay, bx, by = (a[0] - x) * k, a[1] - y, (b[0] - x) * k, b[1] - y
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)

def lookup(zones, lat, lon, reach=0.5):
    for tz, poly, (x0, y0, x1, y1) in zones:
        if x0 <= lon <= x1 and y0 <= lat <= y1 and in_poly(lon, lat, poly):
            return tz
    best, best_d = None, reach
    for tz, poly, (x0, y0, x1, y1) in zones:
        if x0 - reach <= lon <= x1 + reach and y0 - reach <= lat <= y1 + reach:
            ring = poly[0]
            for i in range(len(ring) - 1):
                d = segment_distance(lon, lat, ring[i], ring[i + 1])
                if d < best_d:
                    best, best_d = tz, d
    return best

def read_dbf(path):
    # A dBase table, as in a shapefile: a header, 32-byte field descriptors, fixed-width records.
    f = open(path, "rb")
    head = f.read(32)
    count, header_length, record_length = struct.unpack("<IHH", head[4:12])
    fields = []
    while True:
        d = f.read(32)
        if d[0] == 0x0D:
            break
        fields.append((d[:11].split(b"\0")[0].decode(), d[16]))
    f.seek(header_length)
    rows = []
    for _ in range(count):
        record = f.read(record_length)
        if record[:1] == b"*":  # deleted
            continue
        row, pos = {}, 1
        for name, size in fields:
            row[name] = record[pos:pos + size].decode("utf-8", "replace").strip()
            pos += size
        rows.append(row)
    return rows

SMALL = {"de", "del", "la", "le", "les", "da", "do", "dos", "das", "du", "of", "the", "and", "y", "et", "sur", "en", "al", "el"}

def capital(word):
    # The first letter, after any opening bracket: "(east" -> "(East".
    lead = len(word) - len(word.lstrip("("))
    return word[:lead] + word[lead:lead + 1].upper() + word[lead + 1:]

def title(name):
    # "PORT OF SPAIN" -> "Port of Spain", "SAINT-MALO" -> "Saint-Malo".
    words = name.lower().split(" ")
    out = []
    for i, word in enumerate(words):
        parts = word.split("-")
        out.append("-".join(p if (i > 0 and p in SMALL) else capital(p) for p in parts))
    return " ".join(out).replace("( ", "(")

def index_number(text):
    # "8225.0" or "8225.000000" -> "8225".
    return str(int(float(text)))

def country_codes(csv_rows, dbf_path):
    # Country name -> ISO code, learnt from ports both editions share.
    if not dbf_path:
        return {}
    iso = {index_number(r["INDEX_NO"]): r["COUNTRY"].upper() for r in read_dbf(dbf_path)}
    votes = {}
    for row in csv_rows:
        code = iso.get(index_number(row["World Port Index Number"]))
        if code:
            votes.setdefault(row["Country Code"], {}).setdefault(code, 0)
            votes[row["Country Code"]][code] += 1
    return {name: max(codes, key=codes.get) for name, codes in votes.items()}

def read_ports(path, dbf_path=None):
    # (index number, name, ISO country, latitude, longitude) from either edition.
    if path.lower().endswith(".dbf"):
        for row in read_dbf(path):
            yield (index_number(row["INDEX_NO"]), title(row["PORT_NAME"]), row["COUNTRY"].upper(),
                   row["LATITUDE"], row["LONGITUDE"])
        return
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    # Column names as in NGA's UpdatedPub150.csv; stop rather than guess if they differ.
    needed = ["World Port Index Number", "Main Port Name", "UN/LOCODE", "Latitude", "Longitude"]
    missing = [c for c in needed if c not in rows[0]]
    if missing:
        raise SystemExit("Missing columns %s; columns are %s" % (missing, list(rows[0])))
    codes = country_codes(rows, dbf_path)
    for row in rows:
        locode = row["UN/LOCODE"].replace(" ", "").upper()
        country = codes.get(row["Country Code"]) or (locode[:2] if len(locode) >= 2 and locode[:2].isalpha() else "")
        yield (index_number(row["World Port Index Number"]), row["Main Port Name"].strip(), country,
               row["Latitude"], row["Longitude"])

def main():
    if sys.argv[1] == "--test":
        zones = load_zones(sys.argv[2])
        for name, lat, lon, want in [("Bali (Benoa)", -8.745, 115.215, "Asia/Makassar"),
                                     ("Phuket", 7.88, 98.27, "Asia/Bangkok"),
                                     ("Singapore", 1.265, 103.84, "Asia/Singapore")]:
            got = lookup(zones, lat, lon)
            print(name, got, "ok" if got == want else "WANT " + want)
        return
    wpi_path, zones_path, ports_out, table_out = sys.argv[1:5]
    dbf_path = sys.argv[5] if len(sys.argv) > 5 else None
    overrides_path = __file__.rsplit("/", 1)[0] + "/port-name-overrides.csv"
    try:
        overrides = {row["wpi_number"]: row["name"] for row in csv.DictReader(open(overrides_path, encoding="utf-8"))}
    except FileNotFoundError:
        overrides = {}
    zones = load_zones(zones_path)
    ports, table, unplaced = [], [], []
    for number, name, country, lat_text, lon_text in read_ports(wpi_path, dbf_path):
        try:
            lat, lon = float(lat_text), float(lon_text)
        except ValueError:
            unplaced.append(name); continue
        tz = lookup(zones, lat, lon)
        if tz is None:
            unplaced.append(name); continue
        entry = {"i": int(number), "n": overrides.get(number, name), "c": country,
                 "la": round(lat, 4), "lo": round(lon, 4), "tz": tz}
        if number in overrides:
            entry["a"] = name
        ports.append(entry)
        table.append([number, overrides.get(number, name), name, country, round(lat, 4), round(lon, 4), tz])
    ports.sort(key=lambda p: p["n"])
    json.dump({"source": "NGA World Port Index (public domain); time zones from timezone-boundary-builder, "
                         "(c) OpenStreetMap contributors, ODbL", "ports": ports},
              open(ports_out, "w"), separators=(",", ":"), ensure_ascii=False)
    with open(table_out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["wpi_number", "name", "index_name", "country", "latitude", "longitude", "time_zone"])
        w.writerows(sorted(table, key=lambda r: int(r[0]) if str(r[0]).isdigit() else 0))
    print(len(ports), "ports;", sum(1 for p in ports if not p["c"]), "without a country;",
          len(unplaced), "left out with no time zone within 0.5 degrees:", ", ".join(unplaced[:20]))

main()
