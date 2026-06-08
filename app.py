import math

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QSpinBox,
    QSizePolicy, QSlider, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import calculator
from calculator import INPUT_CONFIG, OUTPUT_CONFIG

_BG      = '#1E1E2E'
_SURFACE = '#252535'
_OVERLAY = '#313244'
_BORDER  = '#45475A'
_TEXT    = '#CDD6F4'
_SUBTEXT = '#A6ADC8'
_MUTED   = '#6C7086'
_ACCENT  = '#89B4FA'
_ACCENT2 = '#FAB387'

DARK_STYLE = f"""
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-size: 11px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {_BG};
    border: none;
}}
QGroupBox {{
    border: 1px solid {_BORDER};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 6px;
    font-weight: bold;
    color: {_SUBTEXT};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}
QDoubleSpinBox, QSpinBox {{
    background: {_OVERLAY};
    border: 1px solid {_BORDER};
    border-radius: 3px;
    color: {_TEXT};
    padding: 1px 3px;
    selection-background-color: {_ACCENT};
    selection-color: {_BG};
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    width: 14px;
    background: {_BORDER};
    border: none;
    border-radius: 2px;
}}
QComboBox {{
    background: {_OVERLAY};
    border: 1px solid {_BORDER};
    border-radius: 3px;
    color: {_TEXT};
    padding: 1px 4px;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {_OVERLAY};
    color: {_TEXT};
    selection-background-color: {_ACCENT};
    selection-color: {_BG};
    border: 1px solid {_BORDER};
}}
QSlider::groove:horizontal {{
    height: 3px;
    background: {_OVERLAY};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {_ACCENT};
    width: 10px;
    height: 10px;
    margin: -4px 0;
    border-radius: 5px;
}}
QSlider::sub-page:horizontal {{
    background: {_ACCENT};
    border-radius: 2px;
    opacity: 0.6;
}}
QPushButton {{
    background: {_OVERLAY};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    color: {_TEXT};
    padding: 2px 8px;
}}
QPushButton:hover {{
    background: {_BORDER};
    border-color: {_ACCENT};
}}
QPushButton:checked {{
    background: {_ACCENT};
    color: {_BG};
    border-color: {_ACCENT};
    font-weight: bold;
}}
QScrollBar:vertical {{
    background: {_SURFACE};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {_BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {_SURFACE};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {_BORDER};
    border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QLabel {{ background: transparent; }}
"""


class GraphPanel(QWidget):
    _ZONE_CMAP = {
        'extra_mass': 'RdYlGn',
        'ld_max':     'RdYlGn',
        'mass_ratio': 'RdYlGn',
        'J':          'RdYlGn',
    }
    _DEFAULT_CMAP = 'viridis'

    def __init__(self, mode: str = '3d', parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._mode = mode

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # ---- header ----
        header = QHBoxLayout()
        header.setContentsMargins(2, 2, 2, 0)
        header.setSpacing(4)

        self._mode_btn = QPushButton()
        self._mode_btn.setFixedWidth(34)
        self._mode_btn.setFixedHeight(20)
        self._mode_btn.setCheckable(True)
        self._mode_btn.setChecked(mode == '3d')
        self._mode_btn.setToolTip("Switch between 2D line and 3D heatmap")
        self._mode_btn.clicked.connect(self._toggle_mode)
        self._update_mode_btn_label()
        header.addWidget(self._mode_btn)

        input_keys  = list(INPUT_CONFIG.keys())
        output_keys = list(OUTPUT_CONFIG.keys())

        x_lbl = QLabel("X:")
        x_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 10px;")
        header.addWidget(x_lbl)
        self._x_combo = QComboBox()
        self._x_combo.setFixedHeight(20)
        for k, cfg in INPUT_CONFIG.items():
            lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
            self._x_combo.addItem(lbl, k)
        self._x_combo.setCurrentIndex(input_keys.index('speed'))
        header.addWidget(self._x_combo, stretch=1)

        self._y_label = QLabel("Y:")
        self._y_label.setStyleSheet(f"color: {_MUTED}; font-size: 10px;")
        header.addWidget(self._y_label)
        self._y_combo = QComboBox()
        self._y_combo.setFixedHeight(20)
        header.addWidget(self._y_combo, stretch=1)

        self._z_label = QLabel("Z:")
        self._z_label.setStyleSheet(f"color: {_MUTED}; font-size: 10px;")
        header.addWidget(self._z_label)
        self._z_combo = QComboBox()
        self._z_combo.setFixedHeight(20)
        for k, cfg in OUTPUT_CONFIG.items():
            lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
            self._z_combo.addItem(lbl, k)
        self._z_combo.setCurrentIndex(output_keys.index('extra_mass'))
        header.addWidget(self._z_combo, stretch=1)

        outer.addLayout(header)

        self._figure = Figure(tight_layout=True)
        self._figure.patch.set_facecolor(_BG)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setStyleSheet(f"background: {_BG};")
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self._canvas, stretch=1)

        self._inputs = None
        self._results = None

        self._apply_mode_layout()

        self._x_combo.currentIndexChanged.connect(self._request_redraw)
        self._y_combo.currentIndexChanged.connect(self._request_redraw)
        self._z_combo.currentIndexChanged.connect(self._request_redraw)

    def _toggle_mode(self):
        self._mode = '3d' if self._mode == '2d' else '2d'
        self._mode_btn.setChecked(self._mode == '3d')
        self._update_mode_btn_label()
        self._apply_mode_layout()
        self._request_redraw()

    def _update_mode_btn_label(self):
        self._mode_btn.setText('3D' if self._mode == '3d' else '2D')

    def _apply_mode_layout(self):
        self._y_combo.blockSignals(True)
        self._y_combo.clear()
        if self._mode == '3d':
            for k, cfg in INPUT_CONFIG.items():
                lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
                self._y_combo.addItem(lbl, k)
            self._y_combo.setCurrentIndex(list(INPUT_CONFIG.keys()).index('mass'))
            self._z_label.show()
            self._z_combo.show()
        else:
            for k, cfg in OUTPUT_CONFIG.items():
                lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
                self._y_combo.addItem(lbl, k)
            self._y_combo.setCurrentIndex(0)
            self._z_label.hide()
            self._z_combo.hide()
        self._y_combo.blockSignals(False)

    def _request_redraw(self):
        if self._inputs is not None:
            self.update_graph(self._inputs, self._results)

    def update_graph(self, inputs: dict, results: dict):
        self._inputs = inputs
        self._results = results
        if self._mode == '2d':
            self._draw_2d(inputs, results)
        else:
            self._draw_3d(inputs, results)

    def _style_axes(self, ax):
        ax.set_facecolor(_SURFACE)
        ax.tick_params(colors=_SUBTEXT, labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor(_BORDER)
        ax.xaxis.label.set_color(_SUBTEXT)
        ax.yaxis.label.set_color(_SUBTEXT)

    def _draw_2d(self, inputs, results):
        x_key = self._x_combo.currentData()
        y_key = self._y_combo.currentData()
        if None in (x_key, y_key):
            return

        x_vals, y_vals = calculator.sweep(inputs, x_key, y_key)

        self._figure.clear()
        self._figure.patch.set_facecolor(_BG)
        ax = self._figure.add_subplot(111)
        self._style_axes(ax)

        valid = np.isfinite(y_vals)

        zone_key = OUTPUT_CONFIG[y_key]['zones']
        if zone_key and valid.any():
            y_data_min, y_data_max = float(np.nanmin(y_vals)), float(np.nanmax(y_vals))
            yr = y_data_max - y_data_min if y_data_max != y_data_min else abs(y_data_max) * 0.2 + 0.01
            for lo, hi, bg, _ in calculator.ZONES[zone_key]:
                lo_c = max(lo, y_data_min - yr * 0.2)
                hi_c = min(hi, y_data_max + yr * 0.2)
                if hi_c > lo_c:
                    ax.axhspan(lo_c, hi_c, color=bg, alpha=0.12, zorder=0)

        if valid.any():
            ax.plot(x_vals[valid], y_vals[valid], color=_ACCENT, linewidth=2, zorder=2)

        x_cur = inputs[x_key]
        ax.axvline(x_cur, color=_ACCENT2, linestyle='--', linewidth=1.5,
                   label='Current', zorder=3, alpha=0.9)
        y_cur = results.get(y_key, float('nan'))
        if math.isfinite(y_cur):
            ax.scatter([x_cur], [y_cur], color=_ACCENT2, s=45, zorder=4, edgecolors='none')

        x_cfg = INPUT_CONFIG[x_key]
        y_cfg = OUTPUT_CONFIG[y_key]
        ax.set_xlabel(f"{x_cfg['label']} ({x_cfg['unit']})" if x_cfg['unit'] else x_cfg['label'], fontsize=8)
        ax.set_ylabel(f"{y_cfg['label']} ({y_cfg['unit']})" if y_cfg['unit'] else y_cfg['label'], fontsize=8)
        ax.grid(True, alpha=0.15, color=_SUBTEXT)
        legend = ax.legend(fontsize=7, facecolor=_OVERLAY, edgecolor=_BORDER, labelcolor=_TEXT)

        xmin, xmax = float(x_vals[0]), float(x_vals[-1])
        xr = xmax - xmin if xmax != xmin else abs(xmax) * 0.2 + 0.01
        ax.set_xlim(xmin - xr * 0.03, xmax + xr * 0.03)
        if valid.any():
            ymin, ymax = float(np.nanmin(y_vals)), float(np.nanmax(y_vals))
            y_center = (ymin + ymax) / 2
            data_range = ymax - ymin if ymax != ymin else abs(y_center) * 0.1 + 0.01
            # Span proportional to absolute value so true angle is preserved, data centered
            y_half = max(data_range * 0.6, abs(y_center) * 0.25)
            ax.set_ylim(y_center - y_half, y_center + y_half)

        self._canvas.draw()

    def _draw_3d(self, inputs, results):
        x_key = self._x_combo.currentData()
        y_key = self._y_combo.currentData()
        z_key = self._z_combo.currentData()
        if None in (x_key, y_key, z_key):
            return

        x_vals, y_vals, z_grid = calculator.sweep2d(inputs, x_key, y_key, z_key)

        self._figure.clear()
        self._figure.patch.set_facecolor(_BG)
        ax = self._figure.add_subplot(111)
        self._style_axes(ax)

        valid = np.isfinite(z_grid)
        cmap = self._ZONE_CMAP.get(z_key, self._DEFAULT_CMAP)

        if valid.any():
            vmin = float(np.nanmin(z_grid))
            vmax = float(np.nanmax(z_grid))
            if z_key == 'extra_mass':
                bound = max(abs(vmin), abs(vmax))
                vmin, vmax = -bound, bound
            pcm = ax.pcolormesh(x_vals, y_vals, z_grid,
                                cmap=cmap, vmin=vmin, vmax=vmax, shading='gouraud')
            cb = self._figure.colorbar(pcm, ax=ax, fraction=0.046, pad=0.04)
            z_cfg = OUTPUT_CONFIG[z_key]
            cb.set_label(
                f"{z_cfg['label']} ({z_cfg['unit']})" if z_cfg['unit'] else z_cfg['label'],
                fontsize=7, color=_SUBTEXT)
            cb.ax.tick_params(colors=_SUBTEXT, labelsize=7)
            cb.outline.set_edgecolor(_BORDER)
        else:
            ax.text(0.5, 0.5, 'No valid data', transform=ax.transAxes,
                    ha='center', va='center', color=_MUTED)

        x_cur, y_cur = inputs[x_key], inputs[y_key]
        ax.axvline(x_cur, color='white', linewidth=1.0, linestyle='--', alpha=0.7, zorder=3)
        ax.axhline(y_cur, color='white', linewidth=1.0, linestyle='--', alpha=0.7, zorder=3)
        ax.scatter([x_cur], [y_cur], color='white', s=40, zorder=4,
                   edgecolors=_BORDER, linewidth=0.8)

        ax.set_xlim(x_vals[0], x_vals[-1])
        ax.set_ylim(y_vals[0], y_vals[-1])

        x_cfg = INPUT_CONFIG[x_key]
        y_cfg = INPUT_CONFIG[y_key]
        ax.set_xlabel(f"{x_cfg['label']} ({x_cfg['unit']})" if x_cfg['unit'] else x_cfg['label'], fontsize=8)
        ax.set_ylabel(f"{y_cfg['label']} ({y_cfg['unit']})" if y_cfg['unit'] else y_cfg['label'], fontsize=8)

        self._canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electric Aircraft Design Calculator")
        self.setMinimumSize(1200, 720)

        self._inputs: dict = calculator.default_inputs()
        self._results: dict = {}
        self._updating: bool = False
        self._sliders: dict = {}
        self._spinboxes: dict = {}
        self._output_labels: dict = {}
        self._graph_panels: list = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(self._build_input_panel(), stretch=2)
        root.addWidget(self._build_output_panel(), stretch=8)

        self._recalculate()

    def _build_input_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(240)
        scroll.setMaximumWidth(290)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Design Parameters")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {_TEXT}; padding: 4px 2px 2px 2px;")
        layout.addWidget(title)
        layout.addWidget(self._separator())

        groups = [
            ("Airframe",         ['mass', 'speed', 'density']),
            ("Aerodynamics",     ['e', 'AR', 'cd0']),
            ("Propulsion",       ['motor_efficiency', 'n', 'd']),
            ("Power",            ['battery_density', 'flight_time', 'avionics_power']),
            ("Component Masses", ['m_avionics', 'm_motor']),
        ]

        for group_name, keys in groups:
            grp_label = QLabel(group_name)
            grp_label.setStyleSheet(
                f"font-size: 10px; font-weight: bold; color: {_ACCENT}; "
                "padding: 4px 2px 1px 2px; background: transparent;"
            )
            layout.addWidget(grp_label)
            for key in keys:
                layout.addWidget(self._build_input_row(key))
            layout.addWidget(self._separator())

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_input_row(self, key: str) -> QWidget:
        cfg = INPUT_CONFIG[key]
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(4)

        name_lbl = QLabel(cfg['label'])
        name_lbl.setFixedWidth(108)
        name_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 11px; background: transparent;")
        name_lbl.setToolTip(f"Unit: {cfg['unit'] or '—'}")

        unit_lbl = QLabel(cfg['unit'])
        unit_lbl.setFixedWidth(30)
        unit_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 10px; background: transparent;")
        unit_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        spinbox = QDoubleSpinBox()
        spinbox.setRange(cfg['min'], cfg['max'])
        spinbox.setSingleStep(cfg['step'])
        spinbox.setDecimals(cfg['decimals'])
        spinbox.setValue(cfg['default'])
        spinbox.setFixedWidth(76)
        spinbox.setFixedHeight(22)
        spinbox.setAlignment(Qt.AlignRight)

        n_steps = round((cfg['max'] - cfg['min']) / cfg['step'])
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, n_steps)
        slider.setValue(round((cfg['default'] - cfg['min']) / cfg['step']))
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        slider.setFixedHeight(22)

        self._spinboxes[key] = spinbox
        self._sliders[key] = slider

        slider.valueChanged.connect(lambda v, k=key: self._on_slider_changed(k, v))
        spinbox.valueChanged.connect(lambda v, k=key: self._on_spinbox_changed(k, v))

        row.addWidget(name_lbl)
        row.addWidget(unit_lbl)
        row.addWidget(spinbox)
        row.addWidget(slider, stretch=1)
        return widget

    def _build_output_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setSpacing(6)
        vbox.setContentsMargins(0, 0, 0, 0)

        outputs_group = QGroupBox("Calculated Outputs")
        grid = QGridLayout(outputs_group)
        grid.setSpacing(2)
        grid.setContentsMargins(8, 10, 8, 6)

        priority = ['extra_mass', 'mass_ratio', 'ld_max', 'J']
        rest = [k for k in OUTPUT_CONFIG if k not in priority]
        ordered = priority + rest

        col_sets = [(0, 1, 2), (4, 5, 6)]
        grid.setColumnMinimumWidth(3, 12)
        for col, stretch in [(0, 3), (1, 2), (2, 1), (3, 0), (4, 3), (5, 2), (6, 1)]:
            grid.setColumnStretch(col, stretch)

        half = math.ceil(len(ordered) / 2)
        for i, key in enumerate(ordered):
            row_idx = i % half
            cols = col_sets[0] if i < half else col_sets[1]
            cfg = OUTPUT_CONFIG[key]

            name_lbl = QLabel(cfg['label'])
            name_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            name_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 11px; background: transparent;")

            val_lbl = QLabel("---")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setMinimumWidth(72)
            val_lbl.setFixedHeight(20)
            val_lbl.setFont(QFont("monospace"))
            val_lbl.setStyleSheet(
                f"background: {_OVERLAY}; color: {_SUBTEXT}; "
                f"border: 1px solid {_BORDER}; border-radius: 3px; padding: 0px 4px;"
            )

            unit_lbl = QLabel(cfg['unit'])
            unit_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            unit_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 10px; background: transparent;")

            grid.addWidget(name_lbl, row_idx, cols[0])
            grid.addWidget(val_lbl,  row_idx, cols[1])
            grid.addWidget(unit_lbl, row_idx, cols[2])
            self._output_labels[key] = val_lbl

        outputs_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        vbox.addWidget(outputs_group, stretch=0)

        graph_outer = QGroupBox("Sensitivity Analysis")
        graph_outer_vbox = QVBoxLayout(graph_outer)
        graph_outer_vbox.setContentsMargins(6, 10, 6, 6)
        graph_outer_vbox.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        count_lbl = QLabel("Graphs:")
        count_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 10px; background: transparent;")
        toolbar.addWidget(count_lbl)
        self._graph_count_spin = QSpinBox()
        self._graph_count_spin.setRange(1, 6)
        self._graph_count_spin.setValue(2)
        self._graph_count_spin.setFixedWidth(48)
        self._graph_count_spin.setFixedHeight(22)
        self._graph_count_spin.setAlignment(Qt.AlignCenter)
        self._graph_count_spin.valueChanged.connect(self._set_graph_count)
        toolbar.addWidget(self._graph_count_spin)
        graph_outer_vbox.addLayout(toolbar)

        self._graphs_container = QWidget()
        self._graphs_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._graphs_grid = QGridLayout(self._graphs_container)
        self._graphs_grid.setContentsMargins(0, 0, 0, 0)
        self._graphs_grid.setSpacing(4)
        self._graphs_grid.setColumnStretch(0, 1)
        self._graphs_grid.setColumnStretch(1, 1)

        graph_outer_vbox.addWidget(self._graphs_container, stretch=1)
        vbox.addWidget(graph_outer, stretch=5)

        self._set_graph_count(2)
        p1 = self._graph_panels[1]
        p1._mode_btn.setChecked(False)
        p1._mode = '2d'
        p1._update_mode_btn_label()
        p1._apply_mode_layout()
        p1._y_combo.setCurrentIndex(list(OUTPUT_CONFIG.keys()).index('ld_max'))

        return panel

    _COLS = 2

    def _set_graph_count(self, count: int):
        while len(self._graph_panels) < count:
            panel = GraphPanel(mode='3d')
            self._graph_panels.append(panel)
            if self._results:
                panel.update_graph(self._inputs, self._results)
        while len(self._graph_panels) > count:
            panel = self._graph_panels.pop()
            panel.setParent(None)
            panel.deleteLater()
        self._reflow_graphs()
        QTimer.singleShot(0, self._update_all_graphs)

    def _reflow_graphs(self):
        while self._graphs_grid.count():
            item = self._graphs_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        cols = self._COLS
        n = len(self._graph_panels)
        n_rows = math.ceil(n / cols) if n > 0 else 1
        max_rows = math.ceil(6 / cols)

        for row in range(max_rows):
            self._graphs_grid.setRowStretch(row, 0)
        for row in range(n_rows):
            self._graphs_grid.setRowStretch(row, 1)

        for i, panel in enumerate(self._graph_panels):
            row, col = divmod(i, cols)
            if i == n - 1 and n % cols != 0:
                self._graphs_grid.addWidget(panel, row, 0, 1, cols)
            else:
                self._graphs_grid.addWidget(panel, row, col)

    def _update_all_graphs(self):
        for panel in self._graph_panels:
            panel.update_graph(self._inputs, self._results)

    def _on_slider_changed(self, key: str, int_val: int):
        if self._updating:
            return
        self._updating = True
        cfg = INPUT_CONFIG[key]
        fval = round(cfg['min'] + int_val * cfg['step'], cfg['decimals'])
        self._spinboxes[key].setValue(fval)
        self._updating = False
        self._inputs[key] = fval
        self._recalculate()

    def _on_spinbox_changed(self, key: str, fval: float):
        if self._updating:
            return
        self._updating = True
        cfg = INPUT_CONFIG[key]
        n_steps = round((cfg['max'] - cfg['min']) / cfg['step'])
        int_val = max(0, min(round((fval - cfg['min']) / cfg['step']), n_steps))
        self._sliders[key].setValue(int_val)
        self._updating = False
        self._inputs[key] = fval
        self._recalculate()

    def _recalculate(self):
        self._results = calculator.compute(self._inputs)
        self._update_outputs()
        self._update_all_graphs()

    def _update_outputs(self):
        for key, lbl in self._output_labels.items():
            value = self._results.get(key, float('nan'))
            cfg = OUTPUT_CONFIG[key]
            if not math.isfinite(value):
                lbl.setText("---")
                lbl.setStyleSheet(
                    f"background: {_OVERLAY}; color: {_MUTED}; "
                    f"border: 1px solid {_BORDER}; border-radius: 3px; "
                    "padding: 0px 4px; font-family: monospace;"
                )
            else:
                lbl.setText(format(value, cfg['format']))
                bg, fg = calculator.get_color(key, value)
                lbl.setStyleSheet(
                    f"background: {bg}; color: {fg}; "
                    f"border: 1px solid {_BORDER}; border-radius: 3px; "
                    "padding: 0px 4px; font-family: monospace;"
                )

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {_BORDER}; background: {_BORDER};")
        return line
