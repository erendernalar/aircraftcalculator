import math
import numpy as np

INPUT_CONFIG = {
    'mass':             {'label': 'Mass',              'unit': 'kg',     'min': 0.5,   'max': 20.0,  'step': 0.1,   'decimals': 2, 'default': 2.8},
    'speed':            {'label': 'Speed',             'unit': 'm/s',    'min': 5.0,   'max': 80.0,  'step': 0.5,   'decimals': 1, 'default': 27.0},
    'motor_efficiency': {'label': 'Motor Efficiency',  'unit': '',       'min': 0.30,  'max': 0.99,  'step': 0.01,  'decimals': 2, 'default': 0.6},
    'battery_density':  {'label': 'Battery Density',   'unit': 'Wh/kg',  'min': 50.0,  'max': 500.0, 'step': 5.0,   'decimals': 0, 'default': 250.0},
    'flight_time':      {'label': 'Flight Time',       'unit': 'h',      'min': 0.1,   'max': 10.0,  'step': 0.1,   'decimals': 1, 'default': 2.0},
    'avionics_power':   {'label': 'Avionics Power',    'unit': 'W',      'min': 1.0,   'max': 200.0, 'step': 1.0,   'decimals': 0, 'default': 50.0},
    'e':                {'label': 'Oswald Efficiency', 'unit': '',       'min': 0.50,  'max': 0.99,  'step': 0.01,  'decimals': 2, 'default': 0.7},
    'AR':               {'label': 'Aspect Ratio',      'unit': '',       'min': 1.0,   'max': 20.0,  'step': 0.1,   'decimals': 1, 'default': 7.0},
    'cd0':              {'label': 'Drag Coef. CD0',    'unit': '',       'min': 0.005, 'max': 0.100, 'step': 0.001, 'decimals': 3, 'default': 0.03},
    'density':          {'label': 'Air Density',       'unit': 'kg/m³', 'min': 0.80,  'max': 1.30,  'step': 0.01,  'decimals': 2, 'default': 1.2},
    'm_avionics':       {'label': 'Avionics Mass',     'unit': 'kg',     'min': 0.10,  'max': 3.0,   'step': 0.05,  'decimals': 2, 'default': 0.6},
    'm_motor':          {'label': 'Motor Mass',        'unit': 'kg',     'min': 0.05,  'max': 2.0,   'step': 0.05,  'decimals': 2, 'default': 0.3},
    'n':                {'label': 'Prop Speed',        'unit': 'rev/s',  'min': 10.0,  'max': 500.0, 'step': 5.0,   'decimals': 0, 'default': 150.0},
    'd':                {'label': 'Prop Diameter',     'unit': 'm',      'min': 0.05,  'max': 1.0,   'step': 0.01,  'decimals': 2, 'default': 0.25},
}

OUTPUT_CONFIG = {
    'extra_mass':      {'label': 'Extra Mass',         'unit': 'kg',     'format': '.4f', 'zones': 'extra_mass'},
    'mass_ratio':      {'label': 'Battery/Mass',       'unit': '',       'format': '.3f', 'zones': 'mass_ratio'},
    'ld_max':          {'label': 'L/D max',            'unit': '',       'format': '.3f', 'zones': 'ld_max'},
    'J':               {'label': 'Advance Ratio J',    'unit': '',       'format': '.3f', 'zones': 'J'},
    'drag':            {'label': 'Drag',               'unit': 'N',      'format': '.3f', 'zones': None},
    'prop_power':      {'label': 'Prop Power',         'unit': 'W',      'format': '.2f', 'zones': None},
    'electric_power':  {'label': 'Electric Power',     'unit': 'W',      'format': '.2f', 'zones': None},
    'flight_energy':   {'label': 'Flight Energy',      'unit': 'Wh',     'format': '.2f', 'zones': None},
    'avionics_energy': {'label': 'Avionics Energy',    'unit': 'Wh',     'format': '.2f', 'zones': None},
    'total_energy':    {'label': 'Total Energy',       'unit': 'Wh',     'format': '.2f', 'zones': None},
    'battery_mass':    {'label': 'Battery Mass',       'unit': 'kg',     'format': '.4f', 'zones': None},
    'wing_area':       {'label': 'Wing Area',          'unit': 'm²','format': '.5f', 'zones': None},
    'wing_loading':    {'label': 'Wing Loading',       'unit': 'N/m²', 'format': '.2f', 'zones': None},
    'chord':           {'label': 'Chord',              'unit': 'm',      'format': '.4f', 'zones': None},
    'wingspan':        {'label': 'Wingspan',           'unit': 'm',      'format': '.4f', 'zones': None},
    'wet_area':        {'label': 'Wet Area',           'unit': 'm²','format': '.5f', 'zones': None},
    'structure_mass':  {'label': 'Structure Mass',     'unit': 'kg',     'format': '.4f', 'zones': None},
    'structure_limit': {'label': 'Structure Budget',   'unit': 'kg',     'format': '.4f', 'zones': None},
    'Cl':              {'label': 'CL at L/D max',      'unit': '',       'format': '.4f', 'zones': None},
    'q':               {'label': 'Dynamic Pressure',   'unit': 'Pa',     'format': '.2f', 'zones': None},
    'k':               {'label': 'k (induced drag)',   'unit': '',       'format': '.5f', 'zones': None},
    'speed_kmh':       {'label': 'Speed',              'unit': 'km/h',   'format': '.1f', 'zones': None},
    'rpm':             {'label': 'Prop RPM',           'unit': 'rpm',    'format': '.0f', 'zones': None},
}

ZONES = {
    'extra_mass': [
        (-1e6, 0.0,  '#FF4444', '#FFFFFF'),
        (0.0,  0.1,  '#FFD700', '#333333'),
        (0.1,  1e6,  '#44AA44', '#FFFFFF'),
    ],
    'mass_ratio': [
        (-1e6, 0.15, '#FF4444', '#FFFFFF'),
        (0.15, 0.20, '#FFD700', '#333333'),
        (0.20, 0.40, '#44AA44', '#FFFFFF'),
        (0.40, 0.60, '#FFD700', '#333333'),
        (0.60, 1e6,  '#FF4444', '#FFFFFF'),
    ],
    'ld_max': [
        (-1e6, 6.0,  '#FF4444', '#FFFFFF'),
        (6.0,  10.0, '#FFD700', '#333333'),
        (10.0, 1e6,  '#44AA44', '#FFFFFF'),
    ],
    'J': [
        (-1e6, 0.3, '#FFD700', '#333333'),
        (0.3,  0.8, '#44AA44', '#FFFFFF'),
        (0.8,  1e6, '#FFD700', '#333333'),
    ],
}

_NAN_OUTPUTS = {k: float('nan') for k in OUTPUT_CONFIG}


def compute(inputs: dict) -> dict:
    try:
        mass             = inputs['mass']
        speed            = inputs['speed']
        motor_efficiency = inputs['motor_efficiency']
        battery_density  = inputs['battery_density']
        flight_time      = inputs['flight_time']
        avionics_power   = inputs['avionics_power']
        e                = inputs['e']
        AR               = inputs['AR']
        cd0              = inputs['cd0']
        density          = inputs['density']
        m_avionics       = inputs['m_avionics']
        m_motor          = inputs['m_motor']
        n                = inputs['n']
        d                = inputs['d']

        k               = 1.0 / (math.pi * e * AR)
        ld_max          = (1.0 / k / cd0) ** 0.5 / 2.0
        Cl              = (cd0 / k) ** 0.5
        q               = 0.5 * density * speed ** 2
        drag            = mass * 9.81 / ld_max
        prop_power      = drag * speed
        electric_power  = prop_power / motor_efficiency
        flight_energy   = electric_power * flight_time       # Wh
        avionics_energy = avionics_power * flight_time       # Wh
        total_energy    = flight_energy + avionics_energy
        battery_mass    = total_energy / battery_density
        wing_area       = mass * 9.81 / q / Cl
        wing_loading    = mass * 9.81 / wing_area
        chord           = (wing_area / AR) ** 0.5
        wingspan        = AR * chord
        wet_area        = wing_area * 4.0
        structure_mass  = wet_area * 0.0011 * 1020.0
        speed_kmh       = speed * 3.6
        rpm             = n * 60.0
        J               = speed / n / d
        mass_ratio      = battery_mass / mass
        structure_limit = mass - m_avionics - m_motor - battery_mass
        extra_mass      = structure_limit - structure_mass

        return {
            'k': k, 'ld_max': ld_max, 'Cl': Cl, 'q': q,
            'drag': drag, 'prop_power': prop_power, 'electric_power': electric_power,
            'flight_energy': flight_energy, 'avionics_energy': avionics_energy,
            'total_energy': total_energy, 'battery_mass': battery_mass,
            'wing_area': wing_area, 'wing_loading': wing_loading,
            'chord': chord, 'wingspan': wingspan, 'wet_area': wet_area,
            'structure_mass': structure_mass, 'speed_kmh': speed_kmh,
            'rpm': rpm, 'J': J, 'mass_ratio': mass_ratio,
            'structure_limit': structure_limit, 'extra_mass': extra_mass,
        }
    except (ZeroDivisionError, ValueError, OverflowError):
        return dict(_NAN_OUTPUTS)


def sweep2d(inputs: dict, x_key: str, y_key: str, z_key: str, n_points: int = 45):
    """Sweep two inputs over a grid and return z values as a 2D array."""
    x_cfg = INPUT_CONFIG[x_key]
    y_cfg = INPUT_CONFIG[y_key]

    x_cur = inputs[x_key]
    y_cur = inputs[y_key]

    x_lo = max(x_cur * 0.5, x_cfg['min'])
    x_hi = min(x_cur * 1.5, x_cfg['max'])
    y_lo = max(y_cur * 0.5, y_cfg['min'])
    y_hi = min(y_cur * 1.5, y_cfg['max'])

    if x_lo >= x_hi:
        x_lo, x_hi = x_cfg['min'], x_cfg['max']
    if y_lo >= y_hi:
        y_lo, y_hi = y_cfg['min'], y_cfg['max']

    x_vals = np.linspace(x_lo, x_hi, n_points)
    y_vals = np.linspace(y_lo, y_hi, n_points)
    z_grid = np.full((n_points, n_points), np.nan)

    for i, yv in enumerate(y_vals):
        for j, xv in enumerate(x_vals):
            trial = dict(inputs)
            trial[x_key] = float(xv)
            trial[y_key] = float(yv)
            z_grid[i, j] = compute(trial)[z_key]

    return x_vals, y_vals, z_grid


def sweep(inputs: dict, x_key: str, y_key: str, n_points: int = 200):
    cfg = INPUT_CONFIG[x_key]
    x_current = inputs[x_key]
    x_lo = max(x_current * 0.5, cfg['min'])
    x_hi = min(x_current * 1.5, cfg['max'])
    if x_lo >= x_hi:
        x_lo = cfg['min']
        x_hi = cfg['max']

    x_vals = np.linspace(x_lo, x_hi, n_points)
    y_vals = np.full(n_points, np.nan)

    for i, xv in enumerate(x_vals):
        trial = dict(inputs)
        trial[x_key] = float(xv)
        result = compute(trial)
        y_vals[i] = result[y_key]

    return x_vals, y_vals


def get_color(output_key: str, value: float):
    zone_key = OUTPUT_CONFIG.get(output_key, {}).get('zones')
    if zone_key is None or math.isnan(value) or math.isinf(value):
        return '#F5F5F5', '#333333'
    for lo, hi, bg, fg in ZONES[zone_key]:
        if lo <= value < hi:
            return bg, fg
    return '#F5F5F5', '#333333'


def default_inputs() -> dict:
    return {k: v['default'] for k, v in INPUT_CONFIG.items()}
