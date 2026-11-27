# Port time zones

The time zone of each port in the NGA World Port Index, published so the table can be reused under
the Open Database License, as that licence requires.

## Files

- `port-timezones.csv`: one row per port: World Port Index number, display name, the index's own
  name, ISO 3166 country code, latitude, longitude, and IANA time zone. 3,788 ports; 21 offshore
  oil terminals with no time zone within 0.5 degrees are left out.
- `port-timezones.py`: the script that makes the table, and a compact JSON list of the same ports.
- `port-name-overrides.csv`: display names that replace the index's, by World Port Index number
  (Singapore for "Keppel - (East Singapore)"). The script reads it from its own folder.

## How it is made

1. Get the World Port Index: NGA's `UpdatedPub150.csv` from https://msi.nga.mil/Publications/WPI.
   This table was made from the edition dated 6 November 2026 (SHA-256
   8c90ee8a2bfd051b986a672fa55fcc5754f29002e95fb4f41dba46330bd5bcb8). That CSV names countries in
   words; their ISO codes are learnt from the older shapefile edition on HDX,
   https://data.humdata.org/dataset/world-port-index (`WPI.dbf` in `world_port_index.zip`), by
   joining the two on the index number, and otherwise taken from the port's UN/LOCODE.
2. Download `timezones.geojson.zip` from
   https://github.com/evansiroky/timezone-boundary-builder/releases (release 2026f was used) and
   unzip it to `combined.json`.
3. Run `python3 -I port-timezones.py UpdatedPub150.csv combined.json ports.json port-timezones.csv WPI.dbf`.

Each port takes the time zone of the boundary polygon it lies in. A port just offshore of every
polygon takes the nearest one within 0.5 degrees; ports with none that close are left out.

## Licence

This table is made available under the Open Database License (ODbL) v1.0:
https://opendatacommons.org/licenses/odbl/1-0/. Any rights in individual contents of the
database are licensed under the Database Contents License:
https://opendatacommons.org/licenses/dbcl/1-0/.

It contains information from timezone-boundary-builder
(https://github.com/evansiroky/timezone-boundary-builder), © OpenStreetMap contributors, which
is made available under the ODbL.

The port names, countries and positions come from the NGA World Port Index (Pub. 150), a work of
the United States Government, in the public domain in the United States.

The script, `port-timezones.py`, is copyright Founder Technology LLC, under the MIT License (see `LICENSE-MIT`).
