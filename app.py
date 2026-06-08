import json
import math

import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QSpinBox,
    QSizePolicy, QSlider, QStyle, QVBoxLayout, QWidget,
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
    width: 16px;
    background: {_BORDER};
    border-left: 1px solid {_ACCENT};
    subcontrol-origin: border;
}}
QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-position: top right;
    border-bottom: 1px solid {_BG};
}}
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-position: bottom right;
}}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {_ACCENT};
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
    height: 4px;
    background: {_OVERLAY};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {_ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {_ACCENT};
    border-radius: 2px;
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


class _JumpSlider(QSlider):
    """QSlider that jumps directly to the clicked position instead of paging."""
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            val = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                event.x(), self.width()
            )
            self.setValue(val)
        super().mousePressEvent(event)


class _FocusSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that emits a signal when it receives focus."""
    focused = pyqtSignal()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focused.emit()


# ------------------------------------------------------------------ #
# Graph panel
# ------------------------------------------------------------------ #
class GraphPanel(QWidget):
    point_selected = pyqtSignal(str, float, str, float)  # x_key, x_val, y_key, y_val

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
        self._param_ranges = None
        self._apply_mode_layout()

        self._canvas.mpl_connect('button_press_event', self._on_canvas_click)
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

    def _on_canvas_click(self, event):
        if self._mode != '3d' or event.inaxes is None:
            return
        if event.xdata is None or event.ydata is None:
            return
        x_key = self._x_combo.currentData()
        y_key = self._y_combo.currentData()
        if x_key is None or y_key is None:
            return
        x_cfg = (self._param_ranges or {}).get(x_key, INPUT_CONFIG[x_key])
        y_cfg = (self._param_ranges or {}).get(y_key, INPUT_CONFIG[y_key])
        x_val = max(x_cfg['min'], min(x_cfg['max'], event.xdata))
        y_val = max(y_cfg['min'], min(y_cfg['max'], event.ydata))
        self.point_selected.emit(x_key, x_val, y_key, y_val)

    def _request_redraw(self):
        if self._inputs is not None:
            self.update_graph(self._inputs, self._results, self._param_ranges)

    def update_graph(self, inputs: dict, results: dict, param_ranges: dict = None):
        self._inputs = inputs
        self._results = results
        self._param_ranges = param_ranges
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

        x_vals, y_vals = calculator.sweep(inputs, x_key, y_key, ranges=self._param_ranges)

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
        ax.legend(fontsize=7, facecolor=_OVERLAY, edgecolor=_BORDER, labelcolor=_TEXT)

        xmin, xmax = float(x_vals[0]), float(x_vals[-1])
        xr = xmax - xmin if xmax != xmin else abs(xmax) * 0.2 + 0.01
        ax.set_xlim(xmin - xr * 0.03, xmax + xr * 0.03)
        if valid.any():
            ymin, ymax = float(np.nanmin(y_vals)), float(np.nanmax(y_vals))
            y_center = (ymin + ymax) / 2
            data_range = ymax - ymin if ymax != ymin else abs(y_center) * 0.1 + 0.01
            y_half = max(data_range * 0.6, abs(y_center) * 0.25)
            ax.set_ylim(y_center - y_half, y_center + y_half)

        self._canvas.draw()

    def _draw_3d(self, inputs, results):
        x_key = self._x_combo.currentData()
        y_key = self._y_combo.currentData()
        z_key = self._z_combo.currentData()
        if None in (x_key, y_key, z_key):
            return

        x_vals, y_vals, z_grid = calculator.sweep2d(inputs, x_key, y_key, z_key, ranges=self._param_ranges)

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


# ------------------------------------------------------------------ #
# Main window
# ------------------------------------------------------------------ #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electric Aircraft Design Calculator")
        self.setMinimumSize(1200, 720)

        self._inputs: dict = calculator.default_inputs()
        self._results: dict = {}
        self._updating: bool = False
        self._value_edits: dict = {}
        self._sliders: dict = {}
        self._range_mins: dict = {}
        self._range_maxs: dict = {}
        self._range_steps: dict = {}
        self._param_ranges: dict = {
            k: {'min': cfg['min'], 'max': cfg['max'], 'step': cfg['step']}
            for k, cfg in INPUT_CONFIG.items()
        }
        self._output_labels: dict = {}
        self._graph_panels: list = []

        self._recalc_timer = QTimer()
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.timeout.connect(self._recalculate)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(self._build_input_panel(), stretch=0)
        root.addWidget(self._build_output_panel(), stretch=1)

        self._build_menu()
        self._recalculate()

    # ------------------------------------------------------------------ #
    # Input panel
    # ------------------------------------------------------------------ #
    def _build_input_panel(self) -> QWidget:
        outer = QWidget()
        outer.setFixedWidth(280)
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # Scrollable param list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Design Parameters")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {_TEXT}; padding: 2px;")
        layout.addWidget(title)

        groups = [
            ("Airframe",         ['mass', 'speed', 'density']),
            ("Aerodynamics",     ['e', 'AR', 'cd0']),
            ("Propulsion",       ['motor_efficiency', 'n', 'd']),
            ("Power",            ['battery_density', 'flight_time', 'avionics_power']),
            ("Component Masses", ['m_avionics', 'm_motor']),
        ]

        for group_name, keys in groups:
            layout.addWidget(self._build_group_card(group_name, keys))

        layout.addStretch()
        scroll.setWidget(container)
        vbox.addWidget(scroll, stretch=1)
        return outer

    def _build_group_card(self, name: str, keys: list) -> QWidget:
        card = QWidget()
        card.setObjectName("groupCard")
        card.setAutoFillBackground(True)
        card.setStyleSheet(f"""
            QWidget#groupCard {{
                background-color: {_SURFACE};
                border-radius: 5px;
                border: 1px solid {_BORDER};
            }}
            QWidget#groupCard QWidget {{
                background-color: transparent;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 4, 5, 4)
        layout.setSpacing(0)

        header = QLabel(name)
        header.setStyleSheet(
            f"color: {_ACCENT}; font-size: 10px; font-weight: bold; "
            "background: transparent; border: none; padding-bottom: 3px;"
        )
        layout.addWidget(header)

        for i, key in enumerate(keys):
            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet(f"background: {_BORDER}; max-height: 1px; border: none; margin: 0px 0px;")
                layout.addWidget(sep)
            layout.addWidget(self._build_input_row(key))

        return card

    def _build_input_row(self, key: str) -> QWidget:
        cfg = INPUT_CONFIG[key]
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        vbox = QVBoxLayout(widget)
        vbox.setContentsMargins(0, 4, 0, 4)
        vbox.setSpacing(3)

        # Line 1: label + unit
        top = QHBoxLayout()
        top.setSpacing(4)
        top.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(cfg['label'])
        name_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 11px;")
        name_lbl.setToolTip(f"Unit: {cfg['unit'] or '—'}")
        unit_lbl = QLabel(cfg['unit'] or '')
        unit_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 10px;")
        top.addWidget(name_lbl, stretch=1)
        top.addWidget(unit_lbl)
        vbox.addLayout(top)

        # Line 2: slider + value text field
        slider_row = QHBoxLayout()
        slider_row.setSpacing(6)
        slider_row.setContentsMargins(0, 0, 0, 0)

        n_steps = round((cfg['max'] - cfg['min']) / cfg['step'])
        slider = _JumpSlider(Qt.Horizontal)
        slider.setRange(0, n_steps)
        slider.setValue(round((cfg['default'] - cfg['min']) / cfg['step']))
        slider.setFixedHeight(18)
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        val_edit = QLineEdit()
        val_edit.setText(format(cfg['default'], ".2f"))
        val_edit.setFixedWidth(58)
        val_edit.setFixedHeight(18)
        val_edit.setAlignment(Qt.AlignRight)
        val_edit.setStyleSheet(
            f"font-size: 10px; color: {_TEXT}; background: {_OVERLAY}; "
            f"border: 1px solid {_ACCENT}; border-radius: 3px; padding: 0px 3px; font-family: monospace;"
        )

        slider_row.addWidget(slider, stretch=1)
        slider_row.addWidget(val_edit)
        vbox.addLayout(slider_row)

        # Line 3: Min / Max / Step
        range_row = QHBoxLayout()
        range_row.setSpacing(3)
        range_row.setContentsMargins(0, 0, 0, 0)

        _rs = f"font-size: 9px; color: {_MUTED};"
        _ss = (f"font-size: 9px; color: {_TEXT}; background: {_OVERLAY}; "
               f"border: 1px solid {_BORDER}; border-radius: 2px; padding: 0px 2px;")

        for lbl_text, attr, val in [("Min", "_min", cfg['min']),
                                     ("Max", "_max", cfg['max']),
                                     ("Stp", "_stp", cfg['step'])]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(_rs)
            lbl.setFixedWidth(18)
            sp = QDoubleSpinBox()
            sp.setDecimals(2)
            sp.setRange((1e-2 if attr == "_stp" else -1e9), 1e9)
            sp.setValue(val)
            sp.setFixedHeight(16)
            sp.setFixedWidth(56)
            sp.setAlignment(Qt.AlignRight)
            sp.setButtonSymbols(QDoubleSpinBox.PlusMinus)
            sp.setStyleSheet(_ss)
            range_row.addWidget(lbl)
            range_row.addWidget(sp)
            if attr == "_min":
                min_spin = sp
            elif attr == "_max":
                max_spin = sp
            else:
                step_spin = sp
        vbox.addLayout(range_row)

        self._value_edits[key]  = val_edit
        self._sliders[key]      = slider
        self._range_mins[key]   = min_spin
        self._range_maxs[key]   = max_spin
        self._range_steps[key]  = step_spin

        slider.valueChanged.connect(lambda v, k=key: self._on_slider_changed(k, v))
        val_edit.editingFinished.connect(lambda k=key: self._on_value_edit_changed(k))
        min_spin.valueChanged.connect(lambda v, k=key: self._on_row_range_changed(k))
        max_spin.valueChanged.connect(lambda v, k=key: self._on_row_range_changed(k))
        step_spin.valueChanged.connect(lambda v, k=key: self._on_row_range_changed(k))

        return widget

    # ------------------------------------------------------------------ #
    # Slider control logic
    # ------------------------------------------------------------------ #
    def _on_slider_changed(self, key: str, int_val: int):
        if self._updating:
            return
        r = self._param_ranges[key]
        cfg = INPUT_CONFIG[key]
        fval = round(r['min'] + int_val * r['step'], cfg['decimals'])
        fval = max(r['min'], min(r['max'], fval))
        self._updating = True
        self._value_edits[key].setText(format(fval, ".2f"))
        self._updating = False
        self._inputs[key] = fval
        # Update outputs instantly, debounce the heavier graph redraw
        self._results = calculator.compute(self._inputs)
        self._update_outputs()
        self._recalc_timer.start(80)

    def _on_value_edit_changed(self, key: str):
        if self._updating:
            return
        cfg = INPUT_CONFIG[key]
        r = self._param_ranges[key]
        try:
            fval = float(self._value_edits[key].text())
        except ValueError:
            return
        fval = round(max(r['min'], min(r['max'], fval)), cfg['decimals'])
        self._value_edits[key].setText(format(fval, ".2f"))
        n_steps = min(10000, max(1, round((r['max'] - r['min']) / r['step'])))
        int_val = max(0, min(round((fval - r['min']) / r['step']), n_steps))
        self._updating = True
        self._sliders[key].setValue(int_val)
        self._updating = False
        self._inputs[key] = fval
        self._recalculate_full()

    def _on_row_range_changed(self, key: str):
        new_min  = self._range_mins[key].value()
        new_max  = self._range_maxs[key].value()
        new_step = self._range_steps[key].value()
        if new_max <= new_min or new_step <= 0:
            return
        self._param_ranges[key] = {'min': new_min, 'max': new_max, 'step': new_step}
        slider = self._sliders[key]
        n_steps = min(10000, max(1, round((new_max - new_min) / new_step)))
        slider.blockSignals(True)
        slider.setRange(0, n_steps)
        cur = max(new_min, min(new_max, self._inputs[key]))
        slider.setValue(max(0, min(round((cur - new_min) / new_step), n_steps)))
        slider.blockSignals(False)
        self._recalculate_full()

    # ------------------------------------------------------------------ #
    # Output panel
    # ------------------------------------------------------------------ #
    def _build_output_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setSpacing(6)
        vbox.setContentsMargins(0, 0, 0, 0)

        outputs_group = QGroupBox("Calculated Outputs")
        outputs_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
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
            name_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 11px;")

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
            unit_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 10px;")

            grid.addWidget(name_lbl, row_idx, cols[0])
            grid.addWidget(val_lbl,  row_idx, cols[1])
            grid.addWidget(unit_lbl, row_idx, cols[2])
            self._output_labels[key] = val_lbl

        vbox.addWidget(outputs_group, stretch=0)

        graph_outer = QGroupBox("Sensitivity Analysis")
        graph_outer_vbox = QVBoxLayout(graph_outer)
        graph_outer_vbox.setContentsMargins(6, 10, 6, 6)
        graph_outer_vbox.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        count_lbl = QLabel("Graphs:")
        count_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 10px;")
        toolbar.addWidget(count_lbl)
        self._graph_count_spin = QSpinBox()
        self._graph_count_spin.setRange(1, 6)
        self._graph_count_spin.setValue(2)
        self._graph_count_spin.setFixedWidth(48)
        self._graph_count_spin.setFixedHeight(22)
        self._graph_count_spin.setAlignment(Qt.AlignCenter)
        self._graph_count_spin.setButtonSymbols(QSpinBox.PlusMinus)
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
        vbox.addWidget(graph_outer, stretch=1)

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
            panel.point_selected.connect(self._on_graph_point_selected)
            self._graph_panels.append(panel)
            if self._results:
                panel.update_graph(self._inputs, self._results, self._param_ranges)
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
            panel.update_graph(self._inputs, self._results, self._param_ranges)

    # ------------------------------------------------------------------ #
    # Signal handlers
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # Calculation + display
    # ------------------------------------------------------------------ #
    def _recalculate(self):
        self._results = calculator.compute(self._inputs)
        self._update_outputs()
        self._update_all_graphs()

    def _recalculate_full(self):
        """Used by value edit and range changes — always recalculates immediately."""
        self._recalc_timer.stop()
        self._recalculate()

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

    # ------------------------------------------------------------------ #
    # Graph click → input sync
    # ------------------------------------------------------------------ #
    def _on_graph_point_selected(self, x_key: str, x_val: float, y_key: str, y_val: float):
        self._set_input_value(x_key, x_val)
        self._set_input_value(y_key, y_val)
        self._recalculate_full()

    def _set_input_value(self, key: str, val: float):
        cfg = INPUT_CONFIG[key]
        r = self._param_ranges[key]
        val = round(max(r['min'], min(r['max'], val)), cfg['decimals'])
        self._inputs[key] = val

        n_steps = min(10000, max(1, round((r['max'] - r['min']) / r['step'])))
        int_val = max(0, min(round((val - r['min']) / r['step']), n_steps))
        self._updating = True
        self._sliders[key].setValue(int_val)
        self._value_edits[key].setText(format(val, ".2f"))
        self._updating = False

    # ------------------------------------------------------------------ #
    # File menu
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_state)
        file_menu.addAction(save_action)

        load_action = QAction("Load", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._load_state)
        file_menu.addAction(load_action)

    def _save_state(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save State", "", "Aircraft Calculator (*.acalc);;All Files (*)"
        )
        if not path:
            return
        if not path.endswith(".acalc"):
            path += ".acalc"
        state = {
            "inputs": self._inputs,
            "param_ranges": self._param_ranges,
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load State", "", "Aircraft Calculator (*.acalc);;All Files (*)"
        )
        if not path:
            return
        with open(path) as f:
            state = json.load(f)
        if "inputs" in state:
            self._inputs.update(state["inputs"])
        if "param_ranges" in state:
            self._param_ranges.update(state["param_ranges"])
        self._sync_ui_from_state()
        self._recalculate_full()

    def _sync_ui_from_state(self):
        self._updating = True
        for key in INPUT_CONFIG:
            r = self._param_ranges[key]
            cfg = INPUT_CONFIG[key]
            val = self._inputs.get(key, cfg['default'])

            min_spin  = self._range_mins[key]
            max_spin  = self._range_maxs[key]
            step_spin = self._range_steps[key]
            min_spin.blockSignals(True)
            max_spin.blockSignals(True)
            step_spin.blockSignals(True)
            min_spin.setValue(r['min'])
            max_spin.setValue(r['max'])
            step_spin.setValue(r['step'])
            min_spin.blockSignals(False)
            max_spin.blockSignals(False)
            step_spin.blockSignals(False)

            n_steps = min(10000, max(1, round((r['max'] - r['min']) / r['step'])))
            int_val = max(0, min(round((val - r['min']) / r['step']), n_steps))
            slider = self._sliders[key]
            slider.blockSignals(True)
            slider.setRange(0, n_steps)
            slider.setValue(int_val)
            slider.blockSignals(False)

            self._value_edits[key].setText(format(val, ".2f"))
        self._updating = False
