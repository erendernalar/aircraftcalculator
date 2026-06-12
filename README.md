# Aircraft Calculator

A desktop application for designing and analysing fixed-wing electric UAVs. It combines an aerodynamic design calculator with a searchable propeller database drawn from real wind-tunnel test data.

![Aircraft Calculator](assets/logo.png)

---

## What it does

### Calculator tab

Enter your airframe parameters and the app instantly computes every derived quantity needed to assess whether the design is viable.

**Inputs (14 parameters)**

| Group | Parameter | Unit |
|---|---|---|
| Airframe | Total mass | kg |
| Airframe | Cruise speed | m/s |
| Airframe | Air density | kg/m³ |
| Aerodynamics | Oswald efficiency *e* | — |
| Aerodynamics | Aspect ratio AR | — |
| Aerodynamics | Zero-lift drag coefficient Cd0 | — |
| Propulsion | Drivetrain efficiency | — |
| Propulsion | Prop rotation speed *n* | rev/s |
| Propulsion | Prop diameter *d* | m |
| Power | Battery energy density | Wh/kg |
| Power | Required flight time | h |
| Power | Avionics power draw | W |
| Component masses | Avionics mass | kg |
| Component masses | Motor mass | kg |

**Outputs (25 values)**

Every output updates in real time as you move any slider.

| Output | What it tells you |
|---|---|
| **m extra** | Mass budget left for structure after battery, motor and avionics. Green = margin exists, red = over budget. |
| **m ratio** | Battery mass as a fraction of total mass. Healthy range 0.20 – 0.40. |
| **L/D max** | Maximum lift-to-drag ratio from the polar. |
| **J** | Advance ratio — propeller operating point. |
| Drag | Cruise drag force (N) |
| Prop / electric power | Shaft and electrical power at cruise (W) |
| Flight / avionics / total energy | Energy budget (Wh) |
| Battery weight | Battery mass derived from energy budget (kg) |
| Wing area, wingspan, chord | Wing geometry (m, m²) |
| Wing loading W/S | Loading at cruise (kg/m²) |
| Wet area | Wetted surface estimate (m²) |
| Structure mass / limit | Estimated and available structural mass (kg) |
| Dynamic pressure *q* | Dynamic pressure at cruise (Pa) |
| Cl at L/D max | Design lift coefficient |
| Speed | Cruise speed in km/h |
| Prop RPM | Propeller rotational speed |

**Traffic-light colouring** — the four key outputs (m extra, m ratio, L/D max, J) are coloured green / amber / red so problems are visible at a glance without reading the numbers.

**Sensitivity graphs** — up to 6 simultaneous graphs, each independently configurable:

- *2D mode* — sweep any input across its range and plot any output. The current operating point is marked with a dashed line and dot.
- *3D heatmap mode* — sweep two inputs over a grid and display the result as a colour-filled contour map. Click any point on the map to jump the sliders to that combination.

Each graph has independently adjustable min/max/step ranges, so you can zoom into the region that matters.

---

### Prop Database tab

A searchable database of **443 propellers** sourced from UIUC Propeller Data Site wind-tunnel measurements.

**Browsing**
- Filter by diameter, type (Standard, Electric, Multi-Rotor, Folding, etc.) or free-text search.
- The list shows diameter, pitch and type. Click any row to load full data.

**Detail view — Standard graph**
- Left plot: efficiency η, thrust coefficient Ct and power coefficient Cp vs advance ratio J for the selected RPM.
- Right plot: thrust (N) and power (W) vs airspeed (mph) on a dual Y-axis.

**Detail view — Advanced graph**
- *2D mode* — all RPM curves overlaid; the currently selected RPM is highlighted.
- *3D heatmap mode* — RPM on the Y axis, speed or J on X, any output quantity as colour. Isoline labels show exact values. Click any point to snap the RPM slider and highlight the matching data row.

**RPM slider** — scrub through all measured RPM tables. Stats (max efficiency, static thrust, static power, thrust-per-watt) update instantly.

**Data table** — the raw tabulated values for the selected RPM: J, η, Ct, Cp, V, thrust, power, torque, thrust/power, Mach, Reynolds number.

---

## How the physics works

The calculator implements standard fixed-wing aerodynamic relations:

```
k          = 1 / (π · e · AR)                 induced drag factor
L/D_max    = sqrt(1 / k / Cd0) / 2            max lift-to-drag ratio
Cl         = sqrt(Cd0 / k)                    lift coeff at L/D_max
q          = ½ · ρ · V²                       dynamic pressure
Drag       = W / (L/D_max)                    cruise drag
P_prop     = Drag · V                         shaft power
P_elec     = P_prop / η_drive                 electrical power
E_flight   = P_elec · t                       flight energy (Wh)
E_total    = E_flight + P_avionics · t        total energy
m_battery  = E_total / e_battery              battery mass
S_wing     = W / (q · Cl)                     wing area
J          = V / (n · d)                      advance ratio
```

Structure mass is estimated from wetted area using a simple area-density model (S_wet = 4 · S_wing, σ = 1.122 kg/m²).

---

## Requirements

```
Python  ≥ 3.9
PyQt5   ≥ 5.14
matplotlib ≥ 3.6
numpy   ≥ 1.23
Pillow  (only needed to rebuild logo_data.py — not required at runtime)
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running

```bash
python main.py
```

### First launch
On the first run the app scans `prop_data/` and builds `props.db`. A progress bar is shown during this one-time build (a few seconds). All subsequent launches load from the database directly.

### Saving and loading designs
**File → Save** exports your current inputs and slider ranges to a `.acalc` JSON file.  
**File → Load** restores a previously saved design.

---

## File structure

```
aircraftcalculator/
├── main.py               entry point, app icon, palette
├── app.py                main window, calculator tab, sensitivity graphs
├── calculator.py         aerodynamic equations, sweep functions
├── prop_database.py      database backend (parse .dat, SQLite, pickle)
├── prop_database_ui.py   prop database tab UI
├── theme.py              colour palette constants
├── logo_data.py          app logo embedded as base64 (no path dependency)
├── props.db              built automatically on first run
├── assets/
│   ├── logo.png          source logo (1024×1024)
│   └── logo.ico          multi-resolution Windows icon
└── prop_data/
    └── *.dat             UIUC propeller data files
```

---

## Platform notes

| Platform | Notes |
|---|---|
| **Windows** | Use `logo.ico` for taskbar / exe icon. If `props.db` was built on a different machine or numpy version, delete it — the app rebuilds automatically. |
| **Ubuntu / Linux** | `logo.png` is used for the window icon. No extra steps needed. |
| **PyInstaller** | Add `assets/` and `prop_data/` as data files in your `.spec`. The app detects `sys._MEIPASS` automatically. |

---

## Prop data source

Propeller data is from the **UIUC Propeller Data Site** (University of Illinois at Urbana-Champaign, Aerospace Engineering). Files are in the standard `.dat` format with columns: V (mph), J, η, Ct, Cp, ..., thrust (N), power (W), torque (N·m), thrust/power (g/W), Mach, Reynolds, figure of merit.
