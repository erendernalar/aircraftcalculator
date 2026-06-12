"""
Prop database backend.

First run: scans prop_data/*.dat, parses everything, saves to props.db.
All subsequent runs: loads from props.db directly (fast, single file).
Other modules: call get_database() to get the singleton PropDatabase.
"""

import io
import os
import pickle
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prop_data')
_DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'props.db')

VARIANT_LABELS: dict = {
    '':          'Standard',
    'E':         'Electric',
    'SF':        'Slow Flyer',
    'W':         'Wide Chord',
    'N':         'Narrow',
    'MR':        'Multi-Rotor',
    'F':         'Folding',
    'WE':        'Wide Electric',
    'EP':        'Elec. Pusher',
    'EPN':       'Elec. Push. Narrow',
    'PN':        'Pusher Narrow',
    'NN':        'Narrow Narrow',
    'WP':        'Wide Pusher',
    'WPN':       'Wide Push. Narrow',
    'SFR':       'Slow Flyer Rev.',
    'SFR-PC':    'Slow Flyer Rev. PC',
    'MRF-RH':    'Multi-Rotor Fold. RH',
    'R-RH':      'Rev. Right Hand',
    'C':         'Carbon',
    'WSF':       'Wide Slow Flyer',
    'E-3':       'Electric 3-blade',
    '-3':        '3-blade',
    '-4':        '4-blade',
    '(WCAR-T6)': 'Wide Carbon T6',
}


# ------------------------------------------------------------------ #
# Data classes
# ------------------------------------------------------------------ #

@dataclass
class PropRPMData:
    rpm: int
    V_mph: np.ndarray
    J: np.ndarray
    Pe: np.ndarray
    Ct: np.ndarray
    Cp: np.ndarray
    pwr_W: np.ndarray
    torque_Nm: np.ndarray
    thrust_N: np.ndarray
    thr_pwr_gW: np.ndarray
    mach: np.ndarray
    reynolds: np.ndarray
    fom: np.ndarray

    def max_efficiency(self) -> float:
        valid = np.isfinite(self.Pe) & (self.Pe > 0)
        return float(np.max(self.Pe[valid])) if valid.any() else float('nan')

    def static_thrust_N(self) -> float:
        return float(self.thrust_N[0]) if len(self.thrust_N) > 0 else float('nan')

    def max_thrust_N(self) -> float:
        valid = np.isfinite(self.thrust_N)
        return float(np.max(self.thrust_N[valid])) if valid.any() else float('nan')

    def static_power_W(self) -> float:
        return float(self.pwr_W[0]) if len(self.pwr_W) > 0 else float('nan')


@dataclass
class PropData:
    id: int
    filename: str
    display_name: str
    diameter_in: float
    pitch_in: float
    variant: str
    rpms: list = field(default_factory=list)

    def variant_label(self) -> str:
        return VARIANT_LABELS.get(self.variant, self.variant or 'Standard')

    def available_rpms(self) -> list:
        return [r.rpm for r in self.rpms]

    def at_rpm(self, rpm: int) -> Optional[PropRPMData]:
        for r in self.rpms:
            if r.rpm == rpm:
                return r
        return None

    def nearest_rpm(self, rpm: int) -> Optional[PropRPMData]:
        if not self.rpms:
            return None
        return min(self.rpms, key=lambda r: abs(r.rpm - rpm))


# ------------------------------------------------------------------ #
# .dat parser
# ------------------------------------------------------------------ #

def _parse_canonical_name(header: str) -> tuple:
    """'10x3.8SF' -> (10.0, 3.8, 'SF')"""
    m = re.match(r'^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(.*)?$', header, re.IGNORECASE)
    if not m:
        return (0.0, 0.0, header.strip())
    return (float(m.group(1)), float(m.group(2)), (m.group(3) or '').strip())


def _parse_dat_file(filepath: str) -> dict:
    with open(filepath, encoding='latin-1') as f:
        lines = f.readlines()

    header_name = ''
    for line in lines[:5]:
        s = line.strip()
        if s:
            header_name = s.split()[0]
            break

    dia, pitch, variant = _parse_canonical_name(header_name)

    rpm_blocks = []
    current_rpm = None
    rows = []
    in_data = False

    for line in lines:
        rpm_m = re.search(r'PROP RPM\s*=\s*(\d+)', line)
        if rpm_m:
            if current_rpm is not None and rows:
                rpm_blocks.append(_make_block(current_rpm, rows))
            current_rpm = int(rpm_m.group(1))
            rows = []
            in_data = False
            continue

        if 'Adv_Ratio' in line:
            in_data = True
            continue
        if '(mph)' in line and '(Adv_Ratio)' in line:
            continue

        if in_data and current_rpm is not None:
            parts = line.strip().split()
            if len(parts) >= 15:
                try:
                    rows.append([float(p) for p in parts[:15]])
                except ValueError:
                    pass

    if current_rpm is not None and rows:
        rpm_blocks.append(_make_block(current_rpm, rows))

    return {
        'filename':     os.path.basename(filepath),
        'display_name': header_name,
        'diameter':     dia,
        'pitch':        pitch,
        'variant':      variant,
        'variant_label': VARIANT_LABELS.get(variant, variant or 'Standard'),
        'rpm_blocks':   rpm_blocks,
    }


def _make_block(rpm: int, rows: list) -> PropRPMData:
    arr = np.array(rows, dtype=np.float32)
    return PropRPMData(
        rpm=rpm,
        V_mph=arr[:, 0],  J=arr[:, 1],       Pe=arr[:, 2],
        Ct=arr[:, 3],     Cp=arr[:, 4],       pwr_W=arr[:, 8],
        torque_Nm=arr[:, 9], thrust_N=arr[:, 10], thr_pwr_gW=arr[:, 11],
        mach=arr[:, 12],  reynolds=arr[:, 13], fom=arr[:, 14],
    )


# ------------------------------------------------------------------ #
# SQLite helpers
# ------------------------------------------------------------------ #

def _to_blob(obj) -> bytes:
    buf = io.BytesIO()
    pickle.dump(obj, buf)
    return buf.getvalue()


def _from_blob(b: bytes):
    return pickle.loads(b)


def _create_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS props (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT UNIQUE,
            display_name  TEXT,
            diameter      REAL,
            pitch         REAL,
            variant       TEXT,
            variant_label TEXT
        );
        CREATE TABLE IF NOT EXISTS rpm_blocks (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            prop_id INTEGER REFERENCES props(id),
            rpm     INTEGER,
            data    BLOB
        );
        CREATE INDEX IF NOT EXISTS idx_rpm_prop ON rpm_blocks(prop_id);
    """)


def build_database(data_dir: str = _DATA_DIR, db_path: str = _DB_PATH,
                   progress_cb=None):
    """
    Parse all .dat files in data_dir and write to db_path.
    progress_cb(current, total, filename) is called for each file.
    After this runs once the .dat files are no longer needed.
    """
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    _create_schema(conn)

    files = sorted(f for f in os.listdir(data_dir) if f.endswith('.dat'))
    total = len(files)

    for i, fname in enumerate(files):
        if progress_cb:
            progress_cb(i, total, fname)
        try:
            parsed = _parse_dat_file(os.path.join(data_dir, fname))
        except Exception:
            continue

        cur = conn.execute(
            "INSERT INTO props (filename, display_name, diameter, pitch, variant, variant_label) "
            "VALUES (?,?,?,?,?,?)",
            (parsed['filename'], parsed['display_name'], parsed['diameter'],
             parsed['pitch'], parsed['variant'], parsed['variant_label'])
        )
        prop_id = cur.lastrowid
        for block in parsed['rpm_blocks']:
            conn.execute(
                "INSERT INTO rpm_blocks (prop_id, rpm, data) VALUES (?,?,?)",
                (prop_id, block.rpm, _to_blob(block))
            )

    conn.commit()
    conn.close()
    if progress_cb:
        progress_cb(total, total, 'done')


# ------------------------------------------------------------------ #
# PropDatabase — public API for all modules
# ------------------------------------------------------------------ #

class PropDatabase:
    def __init__(self, db_path: str = _DB_PATH, data_dir: str = _DATA_DIR):
        self._db_path = db_path
        self._data_dir = data_dir
        self._prop_cache: dict = {}

        # Auto-build on first run if .dat files exist but db doesn't
        if not os.path.exists(db_path):
            if os.path.isdir(data_dir) and \
               any(f.endswith('.dat') for f in os.listdir(data_dir)):
                build_database(data_dir, db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- Listing & filtering (index only, fast) --

    def list_props(self) -> list:
        if not self.is_ready():
            return []
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT id, filename, display_name, diameter, pitch, variant, variant_label "
                "FROM props ORDER BY diameter, pitch, variant"
            )]

    def filter(self, diameter=None, variant=None, search='') -> list:
        if not self.is_ready():
            return []
        clauses, params = [], []
        if diameter is not None:
            clauses.append("diameter = ?")
            params.append(diameter)
        if variant is not None:
            clauses.append("variant = ?")
            params.append(variant)
        if search:
            clauses.append("(display_name LIKE ? OR variant_label LIKE ?)")
            params += [f'%{search}%', f'%{search}%']
        where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
        sql = (f"SELECT id, filename, display_name, diameter, pitch, variant, variant_label "
               f"FROM props {where} ORDER BY diameter, pitch, variant")
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def unique_diameters(self) -> list:
        if not self.is_ready():
            return []
        with self._conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT diameter FROM props WHERE diameter > 0 ORDER BY diameter")]

    def unique_variants(self) -> list:
        if not self.is_ready():
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT variant, variant_label FROM props ORDER BY variant_label")
            return [(r['variant'], r['variant_label']) for r in rows]

    # -- Full prop data (lazy-loaded and cached) --

    def get_prop(self, prop_id: int) -> Optional[PropData]:
        if prop_id in self._prop_cache:
            return self._prop_cache[prop_id]
        if not self.is_ready():
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM props WHERE id = ?", (prop_id,)).fetchone()
            if row is None:
                return None
            rpms = [_from_blob(r['data']) for r in conn.execute(
                "SELECT data FROM rpm_blocks WHERE prop_id = ? ORDER BY rpm",
                (prop_id,))]
        prop = PropData(
            id=row['id'], filename=row['filename'],
            display_name=row['display_name'], diameter_in=row['diameter'],
            pitch_in=row['pitch'], variant=row['variant'], rpms=rpms,
        )
        self._prop_cache[prop_id] = prop
        return prop

    def is_ready(self) -> bool:
        return os.path.exists(self._db_path)

    def prop_count(self) -> int:
        if not self.is_ready():
            return 0
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM props").fetchone()[0]


# ------------------------------------------------------------------ #
# Module-level singleton
# ------------------------------------------------------------------ #

_db: Optional[PropDatabase] = None


def get_database() -> PropDatabase:
    global _db
    if _db is None:
        _db = PropDatabase()
    return _db
