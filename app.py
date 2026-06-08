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


# ------------------------------------------------------------------ #
# Self-contained graph panel  (2D line  OR  3D heatmap)
# ------------------------------------------------------------------ #
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
        self._mode = mode  # '2d' or '3d'

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- header ----
        header = QHBoxLayout()
        header.setContentsMargins(4, 4, 4, 2)
        header.setSpacing(4)

        # Mode toggle button
        self._mode_btn = QPushButton()
        self._mode_btn.setFixedWidth(36)
        self._mode_btn.setFixedHeight(22)
        self._mode_btn.setCheckable(True)
        self._mode_btn.setChecked(mode == '3d')
        self._mode_btn.setToolTip("Switch between 2D line and 3D heatmap")
        self._mode_btn.clicked.connect(self._toggle_mode)
        self._update_mode_btn_label()
        header.addWidget(self._mode_btn)

        input_keys  = list(INPUT_CONFIG.keys())
        output_keys = list(OUTPUT_CONFIG.keys())

        # X — always an input
        header.addWidget(QLabel("X:"))
        self._x_combo = QComboBox()
        for k, cfg in INPUT_CONFIG.items():
            lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
            self._x_combo.addItem(lbl, k)
        self._x_combo.setCurrentIndex(input_keys.index('speed'))
        header.addWidget(self._x_combo, stretch=1)

        # Y — input in 3D mode, output in 2D mode
        self._y_label = QLabel("Y:")
        header.addWidget(self._y_label)
        self._y_combo = QComboBox()
        header.addWidget(self._y_combo, stretch=1)

        # Z — output, only visible in 3D mode
        self._z_label = QLabel("Z:")
        header.addWidget(self._z_label)
        self._z_combo = QComboBox()
        for k, cfg in OUTPUT_CONFIG.items():
            lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
            self._z_combo.addItem(lbl, k)
        self._z_combo.setCurrentIndex(output_keys.index('extra_mass'))
        header.addWidget(self._z_combo, stretch=1)

        outer.addLayout(header)

        # Canvas
        self._figure = Figure(tight_layout=True)
        self._figure.patch.set_facecolor('#FAFAFA')
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self._canvas, stretch=1)

        self._inputs = None
        self._results = None

        # Build Y combo contents and show/hide Z for initial mode
        self._apply_mode_layout()

        self._x_combo.currentIndexChanged.connect(self._request_redraw)
        self._y_combo.currentIndexChanged.connect(self._request_redraw)
        self._z_combo.currentIndexChanged.connect(self._request_redraw)

    # ---- mode switching ----
    def _toggle_mode(self):
        self._mode = '3d' if self._mode == '2d' else '2d'
        self._mode_btn.setChecked(self._mode == '3d')
        self._update_mode_btn_label()
        self._apply_mode_layout()
        self._request_redraw()

    def _update_mode_btn_label(self):
        self._mode_btn.setText('3D' if self._mode == '3d' else '2D')

    def _apply_mode_layout(self):
        """Rebuild Y combo for the current mode, show/hide Z row."""
        self._y_combo.blockSignals(True)
        self._y_combo.clear()
        if self._mode == '3d':
            # Y = input
            for k, cfg in INPUT_CONFIG.items():
                lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
                self._y_combo.addItem(lbl, k)
            # default to 'mass' for the Y axis
            idx = list(INPUT_CONFIG.keys()).index('mass')
            self._y_combo.setCurrentIndex(idx)
            self._z_label.show()
            self._z_combo.show()
        else:
            # Y = output
            for k, cfg in OUTPUT_CONFIG.items():
                lbl = f"{cfg['label']} ({cfg['unit']})" if cfg['unit'] else cfg['label']
                self._y_combo.addItem(lbl, k)
            self._y_combo.setCurrentIndex(0)  # extra_mass first
            self._z_label.hide()
            self._z_combo.hide()
        self._y_combo.blockSignals(False)

    # ---- drawing ----
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

    def _draw_2d(self, inputs, results):
        x_key = self._x_combo.currentData()
        y_key = self._y_combo.currentData()
        if None in (x_key, y_key):
            return

        x_vals, y_vals = calculator.sweep(inputs, x_key, y_key)

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_facecolor('#FAFAFA')

        valid = np.isfinite(y_vals)

        # Zone background bands
        zone_key = OUTPUT_CONFIG[y_key]['zones']
        if zone_key and valid.any():
            y_data_min, y_data_max = float(np.nanmin(y_vals)), float(np.nanmax(y_vals))
            yr = y_data_max - y_data_min if y_data_max != y_data_min else abs(y_data_max) * 0.2 + 0.01
            for lo, hi, bg, _ in calculator.ZONES[zone_key]:
                lo_c = max(lo, y_data_min - yr * 0.2)
                hi_c = min(hi, y_data_max + yr * 0.2)
                if hi_c > lo_c:
                    ax.axhspan(lo_c, hi_c, color=bg, alpha=0.15, zorder=0)

        if valid.any():
            ax.plot(x_vals[valid], y_vals[valid], color='#1565C0', linewidth=2, zorder=2)

        x_cur = inputs[x_key]
        ax.axvline(x_cur, color='#E65100', linestyle='--', linewidth=1.5,
                   label='Current', zorder=3, alpha=0.85)
        y_cur = results.get(y_key, float('nan'))
        if math.isfinite(y_cur):
            ax.scatter([x_cur], [y_cur], color='#E65100', s=50, zorder=4)

        x_cfg = INPUT_CONFIG[x_key]
        y_cfg = OUTPUT_CONFIG[y_key]
        ax.set_xlabel(f"{x_cfg['label']} ({x_cfg['unit']})" if x_cfg['unit'] else x_cfg['label'], fontsize=8)
        ax.set_ylabel(f"{y_cfg['label']} ({y_cfg['unit']})" if y_cfg['unit'] else y_cfg['label'], fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

        xmin, xmax = float(x_vals[0]), float(x_vals[-1])
        xr = xmax - xmin if xmax != xmin else abs(xmax) * 0.2 + 0.01
        ax.set_xlim(xmin - xr * 0.03, xmax + xr * 0.03)
        if valid.any():
            ymin, ymax = float(np.nanmin(y_vals)), float(np.nanmax(y_vals))
            yr = ymax - ymin if ymax != ymin else abs(ymax) * 0.2 + 0.01
            ax.set_ylim(ymin - yr * 0.15, ymax + yr * 0.15)

        self._canvas.draw()

    def _draw_3d(self, inputs, results):
        x_key = self._x_combo.currentData()
        y_key = self._y_combo.currentData()
        z_key = self._z_combo.currentData()
        if None in (x_key, y_key, z_key):
            return

        x_vals, y_vals, z_grid = calculator.sweep2d(inputs, x_key, y_key, z_key)

        self._figure.clear()
        ax = self._figure.add_subplot(111)

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
                fontsize=7)
            cb.ax.tick_params(labelsize=7)
        else:
            ax.text(0.5, 0.5, 'No valid data', transform=ax.transAxes,
                    ha='center', va='center', color='#888')

        x_cur, y_cur = inputs[x_key], inputs[y_key]
        ax.axvline(x_cur, color='white', linewidth=1.2, linestyle='--', alpha=0.85, zorder=3)
        ax.axhline(y_cur, color='white', linewidth=1.2, linestyle='--', alpha=0.85, zorder=3)
        ax.scatter([x_cur], [y_cur], color='white', s=50, zorder=4,
                   edgecolors='#333', linewidth=0.8)

        ax.set_xlim(x_vals[0], x_vals[-1])
        ax.set_ylim(y_vals[0], y_vals[-1])

        x_cfg = INPUT_CONFIG[x_key]
        y_cfg = INPUT_CONFIG[y_key]
        ax.set_xlabel(f"{x_cfg['label']} ({x_cfg['unit']})" if x_cfg['unit'] else x_cfg['label'], fontsize=8)
        ax.set_ylabel(f"{y_cfg['label']} ({y_cfg['unit']})" if y_cfg['unit'] else y_cfg['label'], fontsize=8)
        ax.tick_params(labelsize=7)

        self._canvas.draw()


# ------------------------------------------------------------------ #
# Main window
# ------------------------------------------------------------------ #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electric Aircraft Design Calculator")
        self.setMinimumSize(1350, 780)

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
        root.addWidget(self._build_output_panel(), stretch=5)

        self._recalculate()

    # ------------------------------------------------------------------ #
    # Input panel
    # ------------------------------------------------------------------ #
    def _build_input_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(360)
        scroll.setMaximumWidth(430)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(3)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Design Parameters")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 2px;")
        layout.addWidget(title)
        layout.addWidget(self._separator())

        groups = [
            ("Airframe",          ['mass', 'speed', 'density']),
            ("Aerodynamics",      ['e', 'AR', 'cd0']),
            ("Propulsion",        ['motor_efficiency', 'n', 'd']),
            ("Power",             ['battery_density', 'flight_time', 'avionics_power']),
            ("Component Masses",  ['m_avionics', 'm_motor']),
        ]

        for group_name, keys in groups:
            grp_label = QLabel(group_name)
            grp_label.setStyleSheet(
                "font-size: 11px; font-weight: bold; color: #555; "
                "padding: 4px 2px 2px 2px;"
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
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(5)

        name_lbl = QLabel(cfg['label'])
        name_lbl.setFixedWidth(128)
        name_lbl.setToolTip(f"Unit: {cfg['unit'] or '—'}")

        unit_lbl = QLabel(cfg['unit'])
        unit_lbl.setFixedWidth(42)
        unit_lbl.setStyleSheet("color: #666; font-size: 11px;")
        unit_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        spinbox = QDoubleSpinBox()
        spinbox.setRange(cfg['min'], cfg['max'])
        spinbox.setSingleStep(cfg['step'])
        spinbox.setDecimals(cfg['decimals'])
        spinbox.setValue(cfg['default'])
        spinbox.setFixedWidth(88)
        spinbox.setAlignment(Qt.AlignRight)

        n_steps = round((cfg['max'] - cfg['min']) / cfg['step'])
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, n_steps)
        slider.setValue(round((cfg['default'] - cfg['min']) / cfg['step']))
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._spinboxes[key] = spinbox
        self._sliders[key] = slider

        slider.valueChanged.connect(lambda v, k=key: self._on_slider_changed(k, v))
        spinbox.valueChanged.connect(lambda v, k=key: self._on_spinbox_changed(k, v))

        row.addWidget(name_lbl)
        row.addWidget(unit_lbl)
        row.addWidget(spinbox)
        row.addWidget(slider, stretch=1)
        return widget

    # ------------------------------------------------------------------ #
    # Output panel
    # ------------------------------------------------------------------ #
    def _build_output_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setSpacing(6)
        vbox.setContentsMargins(0, 0, 0, 0)

        # ---- Outputs grid ----
        outputs_group = QGroupBox("Calculated Outputs")
        outputs_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        grid = QGridLayout(outputs_group)
        grid.setSpacing(3)
        grid.setContentsMargins(8, 8, 8, 8)

        priority = ['extra_mass', 'mass_ratio', 'ld_max', 'J']
        rest = [k for k in OUTPUT_CONFIG if k not in priority]
        ordered = priority + rest

        col_sets = [(0, 1, 2), (4, 5, 6)]
        grid.setColumnMinimumWidth(3, 16)
        for col, stretch in [(0, 3), (1, 2), (2, 1), (3, 0), (4, 3), (5, 2), (6, 1)]:
            grid.setColumnStretch(col, stretch)

        half = math.ceil(len(ordered) / 2)
        for i, key in enumerate(ordered):
            row_idx = i % half
            cols = col_sets[0] if i < half else col_sets[1]
            cfg = OUTPUT_CONFIG[key]

            name_lbl = QLabel(cfg['label'])
            name_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            val_lbl = QLabel("---")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setMinimumWidth(78)
            val_lbl.setFont(QFont("monospace"))
            val_lbl.setStyleSheet(
                "background: #F5F5F5; border: 1px solid #DDD; "
                "border-radius: 3px; padding: 1px 5px;"
            )

            unit_lbl = QLabel(cfg['unit'])
            unit_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            unit_lbl.setStyleSheet("color: #666; font-size: 11px;")

            grid.addWidget(name_lbl, row_idx, cols[0])
            grid.addWidget(val_lbl,  row_idx, cols[1])
            grid.addWidget(unit_lbl, row_idx, cols[2])
            self._output_labels[key] = val_lbl

        vbox.addWidget(outputs_group, stretch=2)

        # ---- Graph area ----
        graph_outer = QGroupBox("Sensitivity Analysis")
        graph_outer.setStyleSheet("QGroupBox { font-weight: bold; }")
        graph_outer_vbox = QVBoxLayout(graph_outer)
        graph_outer_vbox.setContentsMargins(6, 6, 6, 6)
        graph_outer_vbox.setSpacing(4)

        # Toolbar: graph count selector
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Graphs:"))
        self._graph_count_spin = QSpinBox()
        self._graph_count_spin.setRange(1, 6)
        self._graph_count_spin.setValue(2)
        self._graph_count_spin.setFixedWidth(52)
        self._graph_count_spin.setAlignment(Qt.AlignCenter)
        self._graph_count_spin.valueChanged.connect(self._set_graph_count)
        toolbar.addWidget(self._graph_count_spin)
        graph_outer_vbox.addLayout(toolbar)

        # Grid container — no scroll, panels always fill the space
        self._graphs_container = QWidget()
        self._graphs_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._graphs_grid = QGridLayout(self._graphs_container)
        self._graphs_grid.setContentsMargins(0, 0, 0, 0)
        self._graphs_grid.setSpacing(4)
        self._graphs_grid.setColumnStretch(0, 1)
        self._graphs_grid.setColumnStretch(1, 1)

        graph_outer_vbox.addWidget(self._graphs_container, stretch=1)

        vbox.addWidget(graph_outer, stretch=3)

        # Default two panels: speed×mass→extra_mass (3D), speed→ld_max (2D)
        self._set_graph_count(2)
        p1 = self._graph_panels[1]
        p1._mode_btn.setChecked(False)
        p1._mode = '2d'
        p1._update_mode_btn_label()
        p1._apply_mode_layout()
        p1._y_combo.setCurrentIndex(list(OUTPUT_CONFIG.keys()).index('ld_max'))

        return panel

    # ------------------------------------------------------------------ #
    # Graph management
    # ------------------------------------------------------------------ #
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
        # Defer redraw until Qt has finished resizing the remaining panels
        QTimer.singleShot(0, self._update_all_graphs)

    def _reflow_graphs(self):
        # Remove all items from the grid without deleting widgets
        while self._graphs_grid.count():
            item = self._graphs_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        cols = self._COLS
        n = len(self._graph_panels)
        n_rows = math.ceil(n / cols) if n > 0 else 1
        max_rows = math.ceil(6 / cols)  # 6 is the spinbox maximum

        # Reset every possible row to 0 first, then set only active rows
        for row in range(max_rows):
            self._graphs_grid.setRowStretch(row, 0)
        for row in range(n_rows):
            self._graphs_grid.setRowStretch(row, 1)

        for i, panel in enumerate(self._graph_panels):
            row, col = divmod(i, cols)
            # Last panel on an odd count spans both columns
            if i == n - 1 and n % cols != 0:
                self._graphs_grid.addWidget(panel, row, 0, 1, cols)
            else:
                self._graphs_grid.addWidget(panel, row, col)

    def _update_all_graphs(self):
        for panel in self._graph_panels:
            panel.update_graph(self._inputs, self._results)

    # ------------------------------------------------------------------ #
    # Signal handlers
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Calculation + display
    # ------------------------------------------------------------------ #
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
                bg, fg = '#F5F5F5', '#333333'
            else:
                lbl.setText(format(value, cfg['format']))
                bg, fg = calculator.get_color(key, value)
            lbl.setStyleSheet(
                f"background: {bg}; color: {fg}; "
                "border: 1px solid #CCC; border-radius: 3px; "
                "padding: 1px 5px; font-family: monospace;"
            )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #DDD;")
        return line
