"""
Prop Database page UI — standard + advanced graph views.
"""

import math

import numpy as np
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QProgressBar, QPushButton, QSizePolicy,
    QSlider, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import prop_database as db
from theme import _BG, _SURFACE, _OVERLAY, _BORDER, _TEXT, _SUBTEXT, _MUTED, \
                  _ACCENT, _ACCENT2, _GREEN, _RED, _YELLOW

# ── Prop output columns available in advanced graph ────────────────
PROP_OUTPUTS = {
    'Pe':          ('Efficiency η',       ''),
    'Ct':          ('Thrust Coeff. Ct',   ''),
    'Cp':          ('Power Coeff. Cp',    ''),
    'thrust_N':    ('Thrust',             'N'),
    'pwr_W':       ('Power',              'W'),
    'torque_Nm':   ('Torque',             'N·m'),
    'thr_pwr_gW':  ('Thrust/Power',       'g/W'),
    'fom':         ('Figure of Merit',    ''),
    'mach':        ('Mach',               ''),
}

PROP_XAXES = {
    'J':     ('Advance Ratio J', ''),
    'V_mph': ('Speed V',         'mph'),
}


# ------------------------------------------------------------------ #
# DB build thread
# ------------------------------------------------------------------ #

class _BuildThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()

    def __init__(self, data_dir, db_path):
        super().__init__()
        self._data_dir = data_dir
        self._db_path = db_path

    def run(self):
        db.build_database(self._data_dir, self._db_path, self._emit)
        self.finished.emit()

    def _emit(self, cur, total, fname):
        self.progress.emit(cur, total, fname)


# ------------------------------------------------------------------ #
# Advanced graph panel (mirrors calculator GraphPanel, uses prop data)
# ------------------------------------------------------------------ #

class PropAdvancedGraph(QWidget):
    # emits (x_key, x_val, nearest_rpm) when user left-clicks the 3D map
    point_selected = pyqtSignal(str, float, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prop: db.PropData = None
        self._current_rpm: int = 5000
        self._mode = '2d'
        self._last_grid = None   # (x_grid, y_vals, z_grid) saved for click lookup
        self._click_marker = None  # (x, y, z) of last click

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # ── Toolbar ────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self._mode_btn = QPushButton('3D')
        self._mode_btn.setFixedSize(34, 22)
        self._mode_btn.setCheckable(True)
        self._mode_btn.setChecked(False)
        self._mode_btn.setToolTip('Switch 2D / 3D')
        self._mode_btn.clicked.connect(self._toggle_mode)
        header.addWidget(self._mode_btn)

        def _lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"color:{_MUTED};font-size:10px;")
            return l

        header.addWidget(_lbl("X:"))
        self._x_combo = QComboBox()
        self._x_combo.setFixedHeight(22)
        for k, (lbl, unit) in PROP_XAXES.items():
            self._x_combo.addItem(f"{lbl} ({unit})" if unit else lbl, k)
        header.addWidget(self._x_combo, stretch=1)

        self._y_lbl = _lbl("Y:")
        header.addWidget(self._y_lbl)
        self._y_combo = QComboBox()
        self._y_combo.setFixedHeight(22)
        header.addWidget(self._y_combo, stretch=1)

        self._z_lbl = _lbl("Z:")
        header.addWidget(self._z_lbl)
        self._z_combo = QComboBox()
        self._z_combo.setFixedHeight(22)
        for k, (lbl, unit) in PROP_OUTPUTS.items():
            self._z_combo.addItem(f"{lbl} ({unit})" if unit else lbl, k)
        header.addWidget(self._z_combo, stretch=1)

        self._cmap_lbl = _lbl("Color:")
        header.addWidget(self._cmap_lbl)
        self._cmap_combo = QComboBox()
        self._cmap_combo.setFixedHeight(22)
        for cm in ['viridis', 'plasma', 'RdYlGn', 'coolwarm', 'inferno', 'jet']:
            self._cmap_combo.addItem(cm)
        self._cmap_combo.setCurrentText('RdYlGn')
        header.addWidget(self._cmap_combo, stretch=1)

        outer.addLayout(header)

        # ── Canvas ─────────────────────────────────────────────────
        self._figure = Figure(tight_layout=True)
        self._figure.patch.set_facecolor(_BG)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setStyleSheet(f"background:{_BG};")
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self._canvas, stretch=1)

        self._canvas.mpl_connect('button_press_event', self._on_click)
        self._apply_mode_layout()
        self._x_combo.currentIndexChanged.connect(self._on_axis_changed)
        self._y_combo.currentIndexChanged.connect(self._on_axis_changed)
        self._z_combo.currentIndexChanged.connect(self._on_axis_changed)
        self._cmap_combo.currentIndexChanged.connect(self._on_axis_changed)

    # ── Mode toggle ────────────────────────────────────────────────

    def _toggle_mode(self):
        self._mode = '3d' if self._mode == '2d' else '2d'
        self._mode_btn.setChecked(self._mode == '3d')
        self._mode_btn.setText('3D' if self._mode == '3d' else '2D')
        self._click_marker = None
        self._apply_mode_layout()
        self._redraw()

    def _on_axis_changed(self):
        self._click_marker = None
        self._redraw()

    def _on_click(self, event):
        if self._mode != '3d':
            return
        if event.button == 3:
            self._click_marker = None
            self._redraw()
            return
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        if self._last_grid is None:
            return
        x_grid, y_vals, z_grid = self._last_grid
        xi = int(np.clip(np.searchsorted(x_grid, event.xdata), 0, len(x_grid) - 1))
        yi = int(np.clip(np.searchsorted(y_vals, event.ydata), 0, len(y_vals) - 1))
        z_val = float(z_grid[yi, xi])
        self._click_marker = (event.xdata, event.ydata, z_val)
        self._redraw()
        # notify parent to highlight the matching row
        nearest_rpm = int(y_vals[yi])
        x_key = self._x_combo.currentData()
        self.point_selected.emit(x_key, float(x_grid[xi]), nearest_rpm)

    def _apply_mode_layout(self):
        self._y_combo.blockSignals(True)
        self._y_combo.clear()
        if self._mode == '3d':
            # Y = RPM axis (auto), Z = output
            self._y_lbl.setText("Y: RPM (auto)")
            self._z_lbl.show(); self._z_combo.show()
            self._cmap_lbl.show(); self._cmap_combo.show()
        else:
            # Y = output selection
            self._y_lbl.setText("Y:")
            for k, (lbl, unit) in PROP_OUTPUTS.items():
                self._y_combo.addItem(f"{lbl} ({unit})" if unit else lbl, k)
            self._z_lbl.hide(); self._z_combo.hide()
            self._cmap_lbl.hide(); self._cmap_combo.hide()
        self._y_combo.blockSignals(False)

    # ── Public API ─────────────────────────────────────────────────

    def set_prop(self, prop: db.PropData, rpm: int):
        self._prop = prop
        self._current_rpm = rpm
        self._redraw()

    def set_rpm(self, rpm: int):
        self._current_rpm = rpm
        self._redraw()

    # ── Drawing ────────────────────────────────────────────────────

    def _redraw(self):
        if self._prop is None:
            return
        if self._mode == '2d':
            self._draw_2d()
        else:
            self._draw_3d()

    def _style_ax(self, ax):
        ax.set_facecolor(_SURFACE)
        ax.tick_params(colors=_SUBTEXT, labelsize=7)
        for sp in ax.spines.values():
            sp.set_edgecolor(_BORDER)
        ax.xaxis.label.set_color(_SUBTEXT)
        ax.yaxis.label.set_color(_SUBTEXT)
        ax.grid(True, alpha=0.10, color=_SUBTEXT, linewidth=0.6)

    def _draw_2d(self):
        x_key = self._x_combo.currentData()
        y_key = self._y_combo.currentData()
        if not x_key or not y_key:
            return

        self._figure.clear()
        self._figure.patch.set_facecolor(_BG)
        ax = self._figure.add_subplot(111)
        self._style_ax(ax)

        cur_rpm = self._prop.nearest_rpm(self._current_rpm)

        # Draw all RPMs as muted background lines
        for r in self._prop.rpms:
            x = getattr(r, x_key)
            y = getattr(r, y_key)
            valid = np.isfinite(x) & np.isfinite(y)
            if not valid.any():
                continue
            is_cur = (r.rpm == (cur_rpm.rpm if cur_rpm else -1))
            ax.plot(x[valid], y[valid],
                    color=_ACCENT if is_cur else _BORDER,
                    lw=2.0 if is_cur else 0.8,
                    alpha=1.0 if is_cur else 0.5,
                    zorder=3 if is_cur else 1,
                    label=f'{r.rpm:,} RPM' if is_cur else None)

        x_lbl_t, x_unit = PROP_XAXES[x_key]
        y_lbl_t, y_unit = PROP_OUTPUTS[y_key]
        ax.set_xlabel(f"{x_lbl_t} ({x_unit})" if x_unit else x_lbl_t, fontsize=8)
        ax.set_ylabel(f"{y_lbl_t} ({y_unit})" if y_unit else y_lbl_t, fontsize=8)
        ax.set_title(f"{self._prop.display_name}  —  all RPMs", fontsize=8, color=_SUBTEXT)
        ax.legend(fontsize=7, facecolor=_OVERLAY, edgecolor=_BORDER, labelcolor=_TEXT)
        self._canvas.draw()

    def _draw_3d(self):
        x_key = self._x_combo.currentData()
        z_key = self._z_combo.currentData()
        cmap  = self._cmap_combo.currentText()
        if not x_key or not z_key:
            return

        # Build grid: X = x_key values, Y = RPM, Z = z_key values
        rpms = self._prop.rpms
        if not rpms:
            return

        all_x = [getattr(r, x_key) for r in rpms]
        x_min = min(float(x.min()) for x in all_x if len(x))
        x_max = max(float(x.max()) for x in all_x if len(x))
        if x_min >= x_max:
            return
        x_grid = np.linspace(x_min, x_max, 60)
        y_vals = np.array([r.rpm for r in rpms], dtype=float)

        z_rows = []
        for r in rpms:
            x_src = getattr(r, x_key)
            z_src = getattr(r, z_key)
            valid = np.isfinite(x_src) & np.isfinite(z_src)
            if valid.sum() >= 2:
                # NaN outside each RPM's own data range
                z_interp = np.interp(x_grid, x_src[valid], z_src[valid],
                                     left=np.nan, right=np.nan)
                z_rows.append(z_interp)
            else:
                z_rows.append(np.full(len(x_grid), np.nan))
        z_grid = np.array(z_rows)
        self._last_grid = (x_grid, y_vals, z_grid)   # save for click lookup

        self._figure.clear()
        self._figure.patch.set_facecolor(_BG)
        ax = self._figure.add_subplot(111)
        self._style_ax(ax)

        z_lbl_t, z_unit = PROP_OUTPUTS[z_key]
        valid_z = np.isfinite(z_grid)
        if valid_z.any():
            vmin = float(np.nanpercentile(z_grid[valid_z], 2))
            vmax = float(np.nanpercentile(z_grid[valid_z], 98))
            if vmin == vmax:
                vmin -= 0.5; vmax += 0.5
            levels = np.linspace(vmin, vmax, 22)
            XX, YY = np.meshgrid(x_grid, y_vals)
            pcm = ax.contourf(XX, YY, z_grid, levels=levels, cmap=cmap)
            iso = ax.contour(XX, YY, z_grid, levels=levels,
                             colors='white', linewidths=0.5, alpha=0.4)
            ax.clabel(iso, inline=True, fontsize=6, fmt='%.3g', colors='white')
            cb = self._figure.colorbar(pcm, ax=ax, fraction=0.046, pad=0.04)
            cb.set_label(f"{z_lbl_t} ({z_unit})" if z_unit else z_lbl_t,
                         fontsize=7, color=_SUBTEXT)
            cb.ax.tick_params(colors=_SUBTEXT, labelsize=7)
            cb.outline.set_edgecolor(_BORDER)

        # Current RPM line
        nearest = self._prop.nearest_rpm(self._current_rpm)
        if nearest:
            ax.axhline(nearest.rpm, color='white', lw=1.2, linestyle='--', alpha=0.7)

        # Click marker + value annotation
        if self._click_marker is not None:
            cx, cy, cz = self._click_marker
            if np.isfinite(cz):
                ax.scatter([cx], [cy], color='white', s=55, zorder=6,
                           edgecolors=_BG, linewidths=1.2)
                val_str = f"{cz:.4g}"
                if z_unit:
                    val_str += f" {z_unit}"
                ax.annotate(
                    val_str,
                    xy=(cx, cy),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=9, color='white', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.4',
                              facecolor=_OVERLAY, edgecolor=_ACCENT,
                              alpha=0.92),
                    zorder=7,
                )

        x_lbl_t, x_unit = PROP_XAXES[x_key]
        ax.set_xlabel(f"{x_lbl_t} ({x_unit})" if x_unit else x_lbl_t, fontsize=8)
        ax.set_ylabel("RPM", fontsize=8)
        ax.set_title(f"{self._prop.display_name}  —  {z_lbl_t}", fontsize=8, color=_SUBTEXT)
        self._canvas.draw()


# ------------------------------------------------------------------ #
# Standard dual-plot view
# ------------------------------------------------------------------ #

class _StandardGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(tight_layout=True)
        self._figure.patch.set_facecolor(_BG)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setStyleSheet(f"background:{_BG};")
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._canvas)

    def _style_ax(self, ax):
        ax.set_facecolor(_SURFACE)
        ax.tick_params(colors=_SUBTEXT, labelsize=7)
        for sp in ax.spines.values():
            sp.set_edgecolor(_BORDER)
        ax.xaxis.label.set_color(_SUBTEXT)
        ax.yaxis.label.set_color(_SUBTEXT)
        ax.grid(True, alpha=0.10, color=_SUBTEXT, linewidth=0.6)

    def update(self, prop: db.PropData, r: db.PropRPMData):
        self._figure.clear()

        ax1 = self._figure.add_subplot(1, 2, 1)
        ax2 = self._figure.add_subplot(1, 2, 2)
        for ax in (ax1, ax2):
            self._style_ax(ax)

        J = r.J
        v = np.isfinite(J)

        # Left: Pe / Ct / Cp vs J
        if v.any():
            ax1.plot(J[v], r.Pe[v],  color=_GREEN,   lw=2,   label='η (Pe)')
            ax1.plot(J[v], r.Ct[v],  color=_ACCENT,  lw=1.5, label='Ct',  alpha=0.85)
            ax1.plot(J[v], r.Cp[v],  color=_ACCENT2, lw=1.5, label='Cp',  alpha=0.85)
        ax1.set_xlabel('J  (advance ratio)', fontsize=8)
        ax1.set_ylabel('Coefficient', fontsize=8)
        ax1.set_title(f'{r.rpm:,} RPM  —  Coefficients vs J', fontsize=8, color=_SUBTEXT)
        ax1.legend(fontsize=7, facecolor=_OVERLAY, edgecolor=_BORDER, labelcolor=_TEXT)

        # Right: Thrust (N) + Power (W) vs V (mph)  — dual Y axis
        V = r.V_mph
        vv = np.isfinite(V) & np.isfinite(r.thrust_N)

        ax2t = ax2.twinx()
        ax2t.set_facecolor(_SURFACE)
        ax2t.tick_params(colors=_ACCENT2, labelsize=7)
        for sp_name in ['top', 'left', 'bottom']:
            ax2t.spines[sp_name].set_edgecolor(_BORDER)
        ax2t.spines['right'].set_edgecolor(_ACCENT2)

        if vv.any():
            ax2.plot(V[vv],   r.thrust_N[vv], color=_GREEN,   lw=2,   label='Thrust (N)')
            ax2t.plot(V[vv],  r.pwr_W[vv],    color=_ACCENT2, lw=1.5, linestyle='--',
                      label='Power (W)')

        ax2.set_xlabel('V  (mph)', fontsize=8)
        ax2.set_ylabel('Thrust  (N)',  fontsize=8, color=_GREEN)
        ax2.tick_params(axis='y', colors=_GREEN)
        ax2t.set_ylabel('Power  (W)', fontsize=8, color=_ACCENT2)
        ax2.set_title(f'{r.rpm:,} RPM  —  Thrust & Power vs V', fontsize=8, color=_SUBTEXT)

        l1, lb1 = ax2.get_legend_handles_labels()
        l2, lb2 = ax2t.get_legend_handles_labels()
        ax2.legend(l1 + l2, lb1 + lb2,
                   fontsize=7, facecolor=_OVERLAY, edgecolor=_BORDER, labelcolor=_TEXT)

        self._canvas.draw()


# ------------------------------------------------------------------ #
# Prop Database Page
# ------------------------------------------------------------------ #

class PropDatabasePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._database = db.get_database()
        self._current_prop: db.PropData = None
        self._current_rpm: int = 5000
        self._all_rows: list = []

        # Debounce timer — updates plots 120 ms after slider stops
        self._plot_timer = QTimer()
        self._plot_timer.setSingleShot(True)
        self._plot_timer.timeout.connect(self._flush_rpm_update)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._loading_widget = self._build_loading_widget()
        root.addWidget(self._loading_widget)

        self._main_widget = QWidget()
        self._main_widget.hide()
        ml = QVBoxLayout(self._main_widget)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(6)
        ml.addLayout(self._build_toolbar())
        ml.addWidget(self._build_splitter(), stretch=1)
        root.addWidget(self._main_widget, stretch=1)

        self._check_ready()

    # ── Loading screen ─────────────────────────────────────────────

    def _build_loading_widget(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.addStretch()

        title = QLabel("Building Prop Database…")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{_TEXT};font-size:16px;font-weight:600;")
        self._loading_label = QLabel("Initializing…")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setStyleSheet(f"color:{_MUTED};font-size:11px;")
        vbox.addWidget(title)
        vbox.addWidget(self._loading_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setFixedWidth(360)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background:{_OVERLAY}; border:1px solid {_BORDER};
                border-radius:4px; height:8px; text-align:center;
                color:{_TEXT}; font-size:10px;
            }}
            QProgressBar::chunk {{ background:{_GREEN}; border-radius:3px; }}
        """)
        pb_row = QHBoxLayout()
        pb_row.addStretch(); pb_row.addWidget(self._progress_bar); pb_row.addStretch()
        vbox.addLayout(pb_row)
        vbox.addStretch()
        return w

    def _check_ready(self):
        if self._database.is_ready():
            self._show_main()
        else:
            t = _BuildThread(db._DATA_DIR, db._DB_PATH)
            t.progress.connect(self._on_build_progress)
            t.finished.connect(self._on_build_done)
            t.start()
            self._build_thread = t

    def _on_build_progress(self, cur, total, fname):
        if total > 0:
            self._progress_bar.setValue(int(cur / total * 100))
        self._loading_label.setText(f"Parsing {fname}  ({cur} / {total})")

    def _on_build_done(self):
        self._database = db.get_database()
        self._show_main()

    def _show_main(self):
        self._loading_widget.hide()
        self._main_widget.show()
        self._populate_filters()
        self._refresh_list()

    # ── Toolbar ────────────────────────────────────────────────────

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"color:{_MUTED};font-size:10px;")
            return l

        row.addWidget(lbl("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("10x7  or  Electric…")
        self._search_edit.setFixedHeight(26)
        self._search_edit.setFixedWidth(180)
        self._search_edit.textChanged.connect(self._refresh_list)
        row.addWidget(self._search_edit)

        row.addWidget(lbl("Diameter:"))
        self._dia_combo = QComboBox()
        self._dia_combo.setFixedHeight(26)
        self._dia_combo.setFixedWidth(76)
        self._dia_combo.currentIndexChanged.connect(self._refresh_list)
        row.addWidget(self._dia_combo)

        row.addWidget(lbl("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.setFixedHeight(26)
        self._type_combo.setFixedWidth(160)
        self._type_combo.currentIndexChanged.connect(self._refresh_list)
        row.addWidget(self._type_combo)

        row.addStretch()
        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color:{_MUTED};font-size:10px;")
        row.addWidget(self._count_label)
        return row

    def _populate_filters(self):
        self._dia_combo.blockSignals(True)
        self._type_combo.blockSignals(True)
        self._dia_combo.clear()
        self._dia_combo.addItem("All", None)
        for d in self._database.unique_diameters():
            self._dia_combo.addItem(f'{d}"', d)
        self._type_combo.clear()
        self._type_combo.addItem("All", None)
        for variant, label in self._database.unique_variants():
            self._type_combo.addItem(label, variant)
        self._dia_combo.blockSignals(False)
        self._type_combo.blockSignals(False)

    # ── Prop list ──────────────────────────────────────────────────

    def _build_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{_BORDER};}}")

        # Left panel
        left = QWidget()
        left.setMinimumWidth(240)
        left.setMaximumWidth(380)
        vl = QVBoxLayout(left)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        self._prop_table = QTableWidget(0, 3)
        self._prop_table.setHorizontalHeaderLabels(["Diameter", "Pitch", "Type"])
        hh = self._prop_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self._prop_table.verticalHeader().setVisible(False)
        self._prop_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._prop_table.setSelectionMode(QTableWidget.SingleSelection)
        self._prop_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._prop_table.setShowGrid(False)
        self._prop_table.setAlternatingRowColors(True)
        self._prop_table.setStyleSheet(f"""
            QTableWidget {{
                background:{_SURFACE}; alternate-background-color:{_OVERLAY};
                border:1px solid {_BORDER}; border-radius:6px;
                color:{_TEXT}; font-size:11px;
            }}
            QTableWidget::item:selected {{ background:{_ACCENT}; color:{_BG}; }}
            QHeaderView::section {{
                background:{_OVERLAY}; color:{_SUBTEXT}; font-size:10px;
                font-weight:600; border:none; border-bottom:1px solid {_BORDER};
                padding:4px 8px;
            }}
        """)
        self._prop_table.itemSelectionChanged.connect(self._on_prop_selected)
        vl.addWidget(self._prop_table)
        splitter.addWidget(left)

        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([280, 920])
        return splitter

    def _refresh_list(self):
        dia = self._dia_combo.currentData()
        variant = self._type_combo.currentData()
        search = self._search_edit.text().strip()
        self._all_rows = self._database.filter(diameter=dia, variant=variant, search=search)
        self._count_label.setText(f"{len(self._all_rows)} props")

        self._prop_table.blockSignals(True)
        self._prop_table.setRowCount(0)
        for row in self._all_rows:
            r = self._prop_table.rowCount()
            self._prop_table.insertRow(r)

            dia_item = QTableWidgetItem(f'{row["diameter"]}"')
            dia_item.setTextAlignment(Qt.AlignCenter)
            dia_item.setData(Qt.UserRole, row['id'])

            pitch_item = QTableWidgetItem(f'{row["pitch"]}"')
            pitch_item.setTextAlignment(Qt.AlignCenter)

            self._prop_table.setItem(r, 0, dia_item)
            self._prop_table.setItem(r, 1, pitch_item)
            self._prop_table.setItem(r, 2, QTableWidgetItem(row['variant_label']))
            self._prop_table.setRowHeight(r, 22)
        self._prop_table.blockSignals(False)

    def _on_prop_selected(self):
        items = self._prop_table.selectedItems()
        if not items:
            return
        prop_id = self._prop_table.item(items[0].row(), 0).data(Qt.UserRole)
        prop = self._database.get_prop(prop_id)
        if prop:
            self._current_prop = prop
            self._load_prop_detail(prop)

    # ── Detail panel ───────────────────────────────────────────────

    def _build_detail_panel(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(10, 0, 0, 0)
        vbox.setSpacing(6)

        # Title row
        title_row = QHBoxLayout()
        self._detail_title = QLabel("Select a propeller")
        self._detail_title.setStyleSheet(
            f"color:{_TEXT};font-size:14px;font-weight:700;")
        self._detail_subtitle = QLabel("")
        self._detail_subtitle.setStyleSheet(f"color:{_MUTED};font-size:10px;")
        title_row.addWidget(self._detail_title)
        title_row.addStretch()
        title_row.addWidget(self._detail_subtitle)
        vbox.addLayout(title_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{_BORDER};max-height:1px;border:none;")
        vbox.addWidget(sep)

        # RPM slider
        rpm_row = QHBoxLayout()
        rpm_lbl = QLabel("RPM:")
        rpm_lbl.setStyleSheet(f"color:{_SUBTEXT};font-size:11px;font-weight:600;")
        rpm_row.addWidget(rpm_lbl)

        self._rpm_slider = QSlider(Qt.Horizontal)
        self._rpm_slider.setMinimum(1000)
        self._rpm_slider.setMaximum(20000)
        self._rpm_slider.setSingleStep(500)
        self._rpm_slider.setPageStep(1000)
        self._rpm_slider.setValue(self._current_rpm)
        self._rpm_slider.setTickInterval(2000)
        self._rpm_slider.setTickPosition(QSlider.TicksBelow)
        self._rpm_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height:5px; background:{_OVERLAY}; border-radius:3px;
            }}
            QSlider::handle:horizontal {{
                background:{_GREEN}; width:16px; height:16px;
                margin:-6px 0; border-radius:8px;
                border:2px solid {_BG};
            }}
            QSlider::handle:horizontal:hover {{
                background:#5EEDAA;
            }}
            QSlider::sub-page:horizontal {{
                background:{_GREEN}; border-radius:3px; opacity:0.6;
            }}
        """)
        self._rpm_slider.valueChanged.connect(self._on_rpm_slider_moved)
        rpm_row.addWidget(self._rpm_slider, stretch=1)

        self._rpm_value_label = QLabel(f"{self._current_rpm:,}")
        self._rpm_value_label.setFixedWidth(54)
        self._rpm_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._rpm_value_label.setStyleSheet(
            f"color:{_GREEN};font-size:13px;font-weight:700;font-family:monospace;")
        rpm_row.addWidget(self._rpm_value_label)
        rpm_row.addWidget(QLabel("RPM"))
        vbox.addLayout(rpm_row)

        # Stats
        vbox.addWidget(self._build_stats_row())

        # View toggle + stacked graph area
        vbox.addLayout(self._build_view_toggle())
        self._graph_stack = QStackedWidget()
        self._std_graph   = _StandardGraph()
        self._adv_graph   = PropAdvancedGraph()
        self._adv_graph.point_selected.connect(self._on_graph_point_selected)
        self._graph_stack.addWidget(self._std_graph)   # index 0
        self._graph_stack.addWidget(self._adv_graph)   # index 1
        vbox.addWidget(self._graph_stack, stretch=1)

        # Data table
        vbox.addWidget(self._build_data_table())
        return w

    def _build_view_toggle(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(0)
        row.setContentsMargins(0, 0, 0, 0)

        self._std_btn = QPushButton("Standard")
        self._adv_btn = QPushButton("Advanced")
        for btn in (self._std_btn, self._adv_btn):
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setFixedWidth(90)
        self._std_btn.setChecked(True)
        self._std_btn.setStyleSheet(self._toggle_style(True))
        self._adv_btn.setStyleSheet(self._toggle_style(False))

        self._std_btn.clicked.connect(lambda: self._set_view(0))
        self._adv_btn.clicked.connect(lambda: self._set_view(1))

        row.addWidget(self._std_btn)
        row.addWidget(self._adv_btn)
        row.addStretch()
        return row

    def _toggle_style(self, active: bool) -> str:
        if active:
            return (f"QPushButton{{background:{_ACCENT};color:{_BG};border:1px solid {_ACCENT};"
                    f"border-radius:4px;font-weight:600;font-size:10px;padding:2px 8px;}}"
                    f"QPushButton:hover{{background:{_ACCENT};}}")
        return (f"QPushButton{{background:{_OVERLAY};color:{_MUTED};border:1px solid {_BORDER};"
                f"border-radius:4px;font-weight:500;font-size:10px;padding:2px 8px;}}"
                f"QPushButton:hover{{background:{_BORDER};color:{_TEXT};}}")

    def _set_view(self, idx: int):
        self._graph_stack.setCurrentIndex(idx)
        self._std_btn.setStyleSheet(self._toggle_style(idx == 0))
        self._adv_btn.setStyleSheet(self._toggle_style(idx == 1))
        self._std_btn.setChecked(idx == 0)
        self._adv_btn.setChecked(idx == 1)
        if self._current_prop:
            self._update_detail(self._current_prop)

    def _build_stats_row(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._stat_labels = {}
        stats = [
            ('max_eff',    'Max η',         '%'),
            ('static_thr', 'Static Thrust', 'N'),
            ('static_pwr', 'Static Power',  'W'),
            ('thr_pwr',    'Thr / Pwr',     'g/W'),
        ]
        for key, label, unit in stats:
            card = QWidget()
            card.setStyleSheet(
                f"background:{_SURFACE};border:1px solid {_BORDER};border-radius:6px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 5, 10, 5)
            cl.setSpacing(1)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color:{_MUTED};font-size:9px;font-weight:600;"
                "background:transparent;border:none;letter-spacing:0.5px;")
            val = QLabel("—")
            val.setStyleSheet(
                f"color:{_TEXT};font-size:14px;font-weight:700;"
                "font-family:monospace;background:transparent;border:none;")
            u = QLabel(unit)
            u.setStyleSheet(
                f"color:{_MUTED};font-size:9px;background:transparent;border:none;")
            cl.addWidget(lbl); cl.addWidget(val); cl.addWidget(u)
            self._stat_labels[key] = val
            layout.addWidget(card)
        layout.addStretch()
        return w

    def _build_data_table(self) -> QWidget:
        cols = ['J', 'Pe (η)', 'Ct', 'Cp', 'V (mph)',
                'Thrust (N)', 'Power (W)', 'Torque (N·m)',
                'Thr/Pwr (g/W)', 'Mach', 'Reynolds']
        self._data_table = QTableWidget(0, len(cols))
        self._data_table.setHorizontalHeaderLabels(cols)
        self._data_table.verticalHeader().setVisible(False)
        self._data_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._data_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._data_table.setShowGrid(False)
        self._data_table.setAlternatingRowColors(True)
        self._data_table.setFixedHeight(150)
        self._data_table.setStyleSheet(f"""
            QTableWidget {{
                background:{_SURFACE}; alternate-background-color:{_OVERLAY};
                border:1px solid {_BORDER}; border-radius:6px;
                color:{_TEXT}; font-size:10px; font-family:monospace;
            }}
            QTableWidget::item:selected {{ background:{_ACCENT}; color:{_BG}; }}
            QHeaderView::section {{
                background:{_OVERLAY}; color:{_SUBTEXT}; font-size:9px;
                font-weight:600; border:none; border-bottom:1px solid {_BORDER};
                padding:3px 5px;
            }}
        """)
        hh = self._data_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setMinimumSectionSize(48)
        hh.setDefaultSectionSize(80)
        return self._data_table

    # ── Data loading ───────────────────────────────────────────────

    def _on_rpm_slider_moved(self, val: int):
        # Snap to nearest 500
        snapped = round(val / 500) * 500
        self._rpm_slider.blockSignals(True)
        self._rpm_slider.setValue(snapped)
        self._rpm_slider.blockSignals(False)
        self._current_rpm = snapped
        self._rpm_value_label.setText(f"{snapped:,}")

        if self._current_prop:
            # Stats update immediately; plots debounced
            rpm_data = self._current_prop.nearest_rpm(snapped)
            if rpm_data:
                self._update_stats(rpm_data)
                self._update_data_table(rpm_data)
            self._plot_timer.start(120)

    def _flush_rpm_update(self):
        if self._current_prop:
            rpm_data = self._current_prop.nearest_rpm(self._current_rpm)
            if rpm_data:
                self._update_graphs(self._current_prop, rpm_data)

    def _load_prop_detail(self, prop: db.PropData):
        self._detail_title.setText(
            f"{prop.diameter_in}\"  ×  {prop.pitch_in}\"   {prop.variant_label()}")
        rpms = prop.available_rpms()
        self._detail_subtitle.setText(
            f"{prop.filename}   ·   {len(rpms)} RPM tables  "
            f"({rpms[0]:,} – {rpms[-1]:,} RPM)" if rpms else "")

        # Snap to nearest available RPM
        if rpms:
            nearest = min(rpms, key=lambda r: abs(r - self._current_rpm))
            self._current_rpm = nearest
            self._rpm_slider.blockSignals(True)
            self._rpm_slider.setValue(nearest)
            self._rpm_slider.blockSignals(False)
            self._rpm_value_label.setText(f"{nearest:,}")

        self._update_detail(prop)

    def _update_detail(self, prop: db.PropData):
        rpm_data = prop.nearest_rpm(self._current_rpm)
        if rpm_data is None:
            return
        self._update_stats(rpm_data)
        self._update_graphs(prop, rpm_data)
        self._update_data_table(rpm_data)

    def _update_stats(self, r: db.PropRPMData):
        def fmt(v, d=2):
            return f"{v:.{d}f}" if math.isfinite(float(v)) else "—"
        valid_pe = r.Pe[r.Pe > 0]
        self._stat_labels['max_eff'].setText(
            fmt(float(valid_pe.max())) if len(valid_pe) else "—")
        self._stat_labels['static_thr'].setText(fmt(r.thrust_N[0]))
        self._stat_labels['static_pwr'].setText(fmt(r.pwr_W[0], 1))
        self._stat_labels['thr_pwr'].setText(fmt(r.thr_pwr_gW[0], 1))

    def _update_graphs(self, prop: db.PropData, r: db.PropRPMData):
        idx = self._graph_stack.currentIndex()
        if idx == 0:
            self._std_graph.update(prop, r)
        else:
            self._adv_graph.set_prop(prop, self._current_rpm)

    def _on_graph_point_selected(self, x_key: str, x_val: float, rpm: int):
        if self._current_prop is None:
            return
        # Snap RPM slider to the clicked RPM
        nearest = self._current_prop.nearest_rpm(rpm)
        if nearest is None:
            return
        self._current_rpm = nearest.rpm
        self._rpm_slider.blockSignals(True)
        self._rpm_slider.setValue(nearest.rpm)
        self._rpm_slider.blockSignals(False)
        self._rpm_value_label.setText(f"{nearest.rpm:,}")
        self._update_stats(nearest)
        self._update_data_table(nearest)
        # Find and highlight the closest row for x_val
        col = 0 if x_key == 'J' else 4  # col 0 = J, col 4 = V_mph
        src = nearest.J if x_key == 'J' else nearest.V_mph
        if len(src):
            row_idx = int(np.argmin(np.abs(src - x_val)))
            self._data_table.selectRow(row_idx)
            self._data_table.scrollToItem(self._data_table.item(row_idx, col))

    def _update_data_table(self, r: db.PropRPMData):
        n = len(r.J)
        self._data_table.setRowCount(n)

        def cell(v, d=4):
            if not math.isfinite(float(v)):
                return QTableWidgetItem("—")
            item = QTableWidgetItem(f"{v:.{d}f}")
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return item

        for i in range(n):
            self._data_table.setItem(i, 0,  cell(r.J[i]))
            self._data_table.setItem(i, 1,  cell(r.Pe[i]))
            self._data_table.setItem(i, 2,  cell(r.Ct[i]))
            self._data_table.setItem(i, 3,  cell(r.Cp[i]))
            self._data_table.setItem(i, 4,  cell(r.V_mph[i], 2))
            self._data_table.setItem(i, 5,  cell(r.thrust_N[i], 3))
            self._data_table.setItem(i, 6,  cell(r.pwr_W[i], 2))
            self._data_table.setItem(i, 7,  cell(r.torque_Nm[i], 4))
            self._data_table.setItem(i, 8,  cell(r.thr_pwr_gW[i], 2))
            self._data_table.setItem(i, 9,  cell(r.mach[i], 3))
            self._data_table.setItem(i, 10, cell(r.reynolds[i], 0))
            self._data_table.setRowHeight(i, 18)
        self._data_table.resizeColumnsToContents()
