#!/usr/bin/env python3
"""
Battery Cell Modeling GUI — KooRemapper
PySide6 GUI for automated battery K-file generation with capacity estimation.
"""

import sys
import os
import subprocess
import itertools
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QPushButton, QLineEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QProgressBar, QPlainTextEdit, QScrollArea,
    QHeaderView, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPalette, QColor, QFont


# ═══════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class LayerSpec:
    value: float = 0.0
    is_range: bool = False
    range_min: float = 0.0
    range_max: float = 0.0
    steps: int = 3


@dataclass
class ThicknessSet:
    al_cc: float = 0.012
    cathode: float = 0.065
    separator: float = 0.020
    anode: float = 0.070
    cu_cc: float = 0.008
    pouch: float = 0.153
    buffer: float = 0.200


@dataclass
class CellConfig:
    model_type: str = "wound"
    tier: float = 0.0
    mode: str = "swell"
    solid_electrode: bool = True
    solid_elform: int = 1
    cell_width: float = 66.4
    cell_height: float = 89.8
    target_height: float = 0.0
    n_unit_cells: int = 11
    n_winds: int = 10
    flat_ratio: float = 1.3
    thickness: ThicknessSet = field(default_factory=ThicknessSet)
    # Capacity estimation
    cathode_sp_cap: float = 180.0   # mAh/g
    cathode_density: float = 2.50   # g/cm3
    anode_sp_cap: float = 350.0     # mAh/g
    anode_density: float = 1.60     # g/cm3
    loading: float = 0.95
    nominal_voltage: float = 3.7    # V
    # Swelling
    soc: float = 1.0
    nmc_cte: float = 0.04
    graphite_cte: float = 0.10
    # Output
    output_dir: str = ""
    output_prefix: str = "battery"
    label: str = ""


@dataclass
class SweepResult:
    filename: str = ""
    model_type: str = ""
    tier: float = 0.0
    n_layers: int = 0
    target_h: float = 0.0
    actual_h: float = 0.0
    capacity_mah: float = 0.0
    energy_density: float = 0.0
    status: str = "Pending"


# ═══════════════════════════════════════════════════════════════
# Capacity Calculator
# ═══════════════════════════════════════════════════════════════

class CapacityCalculator:
    @staticmethod
    def unit_cell_thickness(cfg: CellConfig) -> float:
        t = cfg.thickness
        if cfg.model_type == "wound":
            return t.al_cc + t.cathode + t.separator + t.anode + t.cu_cc
        else:
            return t.al_cc + 2 * t.cathode + 2 * t.separator + 2 * t.anode + t.cu_cc

    @staticmethod
    def compute_n_layers(cfg: CellConfig) -> int:
        # Fixed layer count — user specifies directly
        return cfg.n_winds if cfg.model_type == "wound" else cfg.n_unit_cells

    @staticmethod
    def compute_actual_height(cfg: CellConfig) -> float:
        n = CapacityCalculator.compute_n_layers(cfg)
        uc = CapacityCalculator.unit_cell_thickness(cfg)
        jelly = uc * n
        return jelly + 2 * cfg.thickness.buffer + 2 * cfg.thickness.pouch

    @staticmethod
    def compute_capacity_mah(cfg: CellConfig) -> float:
        n = CapacityCalculator.compute_n_layers(cfg)
        area_cm2 = (cfg.cell_width / 10.0) * (cfg.cell_height / 10.0)
        cathode_t_cm = cfg.thickness.cathode / 10.0
        cap_per_layer = (area_cm2 * cathode_t_cm * cfg.cathode_density
                         * cfg.cathode_sp_cap * cfg.loading)
        if cfg.model_type == "stacked":
            cap_per_layer *= 2  # double-sided
        return cap_per_layer * n

    @staticmethod
    def compute_energy_density(cfg: CellConfig) -> float:
        cap_mah = CapacityCalculator.compute_capacity_mah(cfg)
        energy_wh = cap_mah * cfg.nominal_voltage / 1000.0
        t = cfg.thickness
        n = CapacityCalculator.compute_n_layers(cfg)
        uc = CapacityCalculator.unit_cell_thickness(cfg)
        area_cm2 = (cfg.cell_width / 10.0) * (cfg.cell_height / 10.0)
        # Mass estimation (g) per unit cell
        mass_uc = area_cm2 * (
            t.al_cc / 10.0 * 2.70 +   # Al density
            t.cu_cc / 10.0 * 8.96 +   # Cu density
            t.cathode / 10.0 * cfg.cathode_density * (2 if cfg.model_type == "stacked" else 1) +
            t.anode / 10.0 * cfg.anode_density * (2 if cfg.model_type == "stacked" else 1) +
            t.separator / 10.0 * 1.10 * (2 if cfg.model_type == "stacked" else 1)
        )
        mass_pouch = area_cm2 * t.pouch / 10.0 * 1.40 * 2  # top + bottom
        total_mass_g = mass_uc * n + mass_pouch
        total_mass_kg = total_mass_g / 1000.0
        if total_mass_kg <= 0:
            return 0.0
        return energy_wh / total_mass_kg


# ═══════════════════════════════════════════════════════════════
# YAML Generator
# ═══════════════════════════════════════════════════════════════

class YamlGenerator:
    @staticmethod
    def generate(cfg: CellConfig, output_dir: Path, filename: str) -> Path:
        t = cfg.thickness
        n = CapacityCalculator.compute_n_layers(cfg)

        yaml_path = output_dir / f"{filename}.yaml"
        output_rel = str(output_dir / filename).replace("\\", "/")

        lines = [
            f"output: {output_rel}",
            f"model_type: {cfg.model_type}",
            f"tier: {cfg.tier}",
            f"phase: 1",
            f"mode: {cfg.mode}",
            f"",
            f"solid_electrode: {'true' if cfg.solid_electrode else 'false'}",
            f"solid_elform:   {cfg.solid_elform}",
            f"airbag_fill:     true",
            f"no_pcm:          true",
            f"no_thermal:      true",
            f"",
            f"geometry:",
            f"  cell_width:   {cfg.cell_width}",
            f"  cell_height:  {cfg.cell_height}",
        ]

        if cfg.model_type == "stacked":
            lines.append(f"  n_unit_cells: {n}")

        lines += [
            f"",
            f"layer_thickness:",
            f"  al_cc:              {t.al_cc:.4f}",
            f"  cathode:            {t.cathode:.4f}",
            f"  separator:          {t.separator:.4f}",
            f"  anode:              {t.anode:.4f}",
            f"  cu_cc:              {t.cu_cc:.4f}",
            f"  pouch:              {t.pouch:.4f}",
            f"  electrolyte_buffer: {t.buffer:.4f}",
            f"",
            f"pouch:",
        ]

        if cfg.model_type == "stacked":
            lines += [
                f"  r_fillet:      2.0",
                f"  n_fillet_segs: 1",
                f"  buf_x:         0.5",
                f"  buf_y:         0.5",
                f"  dome_cap:      true",
            ]
        else:
            lines += [
                f"  r_fillet: 0.5",
            ]

        if cfg.model_type == "wound":
            lines += [
                f"",
                f"wound:",
                f"  flat:       true",
                f"  flat_ratio: {cfg.flat_ratio}",
                f"  n_winds:    {n}",
            ]

        lines += [
            f"",
            f"swelling:",
            f"  soc:          {cfg.soc}",
            f"  nmc_cte:      {cfg.nmc_cte}",
            f"  graphite_cte: {cfg.graphite_cte}",
            f"",
            f"dr_endtim:      0.0005",
            f"dr_tolerance:   1.0e-3",
            f"dr_factor:      0.995",
            f"dr_nrcyck:      250",
            f"",
            f"timestep_safety:   0.67",
            f"output_interval:   5.0e-5",
        ]

        with open(yaml_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        return yaml_path


# ═══════════════════════════════════════════════════════════════
# Sweep Engine
# ═══════════════════════════════════════════════════════════════

class SweepEngine:
    @staticmethod
    def linspace(start: float, stop: float, n: int) -> list:
        if n <= 1:
            return [start]
        return [start + (stop - start) * i / (n - 1) for i in range(n)]

    @staticmethod
    def lhs(n_samples: int, n_dims: int, seed: int = 42) -> list:
        """Latin Hypercube Sampling — returns n_samples × n_dims in [0,1]"""
        rng = random.Random(seed)
        result = []
        for d in range(n_dims):
            perm = list(range(n_samples))
            rng.shuffle(perm)
            col = [(perm[i] + rng.random()) / n_samples for i in range(n_samples)]
            result.append(col)
        # Transpose: list of rows
        return [[result[d][i] for d in range(n_dims)] for i in range(n_samples)]

    @staticmethod
    def expand_ranges(specs: dict, mode: str = "full", n_samples: int = 20) -> list:
        """
        specs: {field_name: LayerSpec}
        mode: "full" = full factorial, "lhs" = Latin Hypercube Sampling
        Returns list of dicts with concrete values.
        """
        range_keys = [k for k, s in specs.items() if s.is_range]
        fixed_keys = [k for k, s in specs.items() if not s.is_range]

        if not range_keys:
            # No ranges: single combination
            return [{k: s.value for k, s in specs.items()}]

        if mode == "lhs" and len(range_keys) >= 1:
            # LHS over range dimensions, fixed for non-range
            samples = SweepEngine.lhs(n_samples, len(range_keys))
            combos = []
            for row in samples:
                combo = {}
                for k in fixed_keys:
                    combo[k] = specs[k].value
                for j, k in enumerate(range_keys):
                    s = specs[k]
                    combo[k] = s.range_min + row[j] * (s.range_max - s.range_min)
                combos.append(combo)
            return combos
        else:
            # Full factorial
            axes = {}
            for name, spec in specs.items():
                if spec.is_range:
                    axes[name] = SweepEngine.linspace(spec.range_min, spec.range_max, spec.steps)
                else:
                    axes[name] = [spec.value]
            keys = list(axes.keys())
            vals = [axes[k] for k in keys]
            return [dict(zip(keys, combo)) for combo in itertools.product(*vals)]


# ═══════════════════════════════════════════════════════════════
# Generator Worker (QThread)
# ═══════════════════════════════════════════════════════════════

class GeneratorWorker(QThread):
    progress = Signal(int, int)
    result_ready = Signal(object)
    log_message = Signal(str)
    error = Signal(str)

    def __init__(self, configs: list, output_dir: Path, exe_path: Path):
        super().__init__()
        self.configs = configs
        self.output_dir = output_dir
        self.exe_path = exe_path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = len(self.configs)
        for i, (cfg, yaml_path) in enumerate(self.configs):
            if self._cancelled:
                break

            self.log_message.emit(f"--- [{i+1}/{total}] Generating: {yaml_path.name} ---")

            try:
                proc = subprocess.Popen(
                    [str(self.exe_path), "battery", str(yaml_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(self.output_dir)
                )
                for line in proc.stdout:
                    text = line.decode(errors='replace').rstrip()
                    if text:
                        self.log_message.emit(text)
                proc.wait()
                status = "OK" if proc.returncode == 0 else f"Error({proc.returncode})"
            except Exception as e:
                status = f"Error: {e}"

            n = CapacityCalculator.compute_n_layers(cfg)
            actual_h = CapacityCalculator.compute_actual_height(cfg)
            cap = CapacityCalculator.compute_capacity_mah(cfg)
            ed = CapacityCalculator.compute_energy_density(cfg)

            result = SweepResult(
                filename=yaml_path.stem,
                model_type=cfg.model_type,
                tier=cfg.tier,
                n_layers=n,
                target_h=cfg.target_height,
                actual_h=actual_h,
                capacity_mah=cap,
                energy_density=ed,
                status=status,
            )
            self.result_ready.emit(result)
            self.progress.emit(i + 1, total)


# ═══════════════════════════════════════════════════════════════
# Custom Widgets
# ═══════════════════════════════════════════════════════════════

class RangeInput(QWidget):
    value_changed = Signal()

    def __init__(self, default: float = 0.0, decimals: int = 4, step: float = 0.001, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.single_spin = QDoubleSpinBox()
        self.single_spin.setDecimals(decimals)
        self.single_spin.setSingleStep(step)
        self.single_spin.setRange(0, 999)
        self.single_spin.setValue(default)
        self.single_spin.setFixedWidth(90)

        self.range_check = QCheckBox("Range")
        self.range_check.setFixedWidth(60)

        self.min_spin = QDoubleSpinBox()
        self.min_spin.setDecimals(decimals)
        self.min_spin.setSingleStep(step)
        self.min_spin.setRange(0, 999)
        self.min_spin.setValue(default * 0.95)
        self.min_spin.setFixedWidth(80)
        self.min_spin.setPrefix("min:")

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setDecimals(decimals)
        self.max_spin.setSingleStep(step)
        self.max_spin.setRange(0, 999)
        self.max_spin.setValue(default * 1.05)
        self.max_spin.setFixedWidth(80)
        self.max_spin.setPrefix("max:")

        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(2, 20)
        self.steps_spin.setValue(3)
        self.steps_spin.setFixedWidth(50)
        self.steps_spin.setPrefix("n:")

        layout.addWidget(self.single_spin)
        layout.addWidget(self.range_check)
        layout.addWidget(self.min_spin)
        layout.addWidget(self.max_spin)
        layout.addWidget(self.steps_spin)

        self.min_spin.hide()
        self.max_spin.hide()
        self.steps_spin.hide()

        self.range_check.toggled.connect(self._toggle_range)
        self.single_spin.valueChanged.connect(lambda: self.value_changed.emit())
        self.min_spin.valueChanged.connect(lambda: self.value_changed.emit())
        self.max_spin.valueChanged.connect(lambda: self.value_changed.emit())
        self.steps_spin.valueChanged.connect(lambda: self.value_changed.emit())

    def _toggle_range(self, checked):
        self.single_spin.setVisible(not checked)
        self.min_spin.setVisible(checked)
        self.max_spin.setVisible(checked)
        self.steps_spin.setVisible(checked)
        self.value_changed.emit()

    def get_spec(self) -> LayerSpec:
        if self.range_check.isChecked():
            return LayerSpec(
                is_range=True,
                range_min=self.min_spin.value(),
                range_max=self.max_spin.value(),
                steps=self.steps_spin.value(),
            )
        return LayerSpec(value=self.single_spin.value())


# ═══════════════════════════════════════════════════════════════
# Input Panel
# ═══════════════════════════════════════════════════════════════

class InputPanel(QWidget):
    config_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Model config
        grp_model = QGroupBox("Model Configuration")
        form_model = QFormLayout(grp_model)
        self.model_type = QComboBox()
        self.model_type.addItems(["wound", "stacked"])
        self.tier = QComboBox()
        self.tier.addItems(["0", "1", "2"])
        self.mode = QComboBox()
        self.mode.addItems(["swell", "bare", "dent", "side"])
        self.elform = QComboBox()
        self.elform.addItems(["1 (reduced)", "2 (full integrated)"])
        self.solid_electrode = QCheckBox()
        self.solid_electrode.setChecked(True)
        form_model.addRow("Model Type:", self.model_type)
        form_model.addRow("Tier:", self.tier)
        form_model.addRow("Mode:", self.mode)
        form_model.addRow("ELFORM:", self.elform)
        self.sweep_mode = QComboBox()
        self.sweep_mode.addItems(["Full Factorial", "LHS (Latin Hypercube)"])
        self.lhs_samples = QSpinBox()
        self.lhs_samples.setRange(5, 500)
        self.lhs_samples.setValue(30)
        form_model.addRow("Solid Electrode:", self.solid_electrode)
        form_model.addRow("Sweep Mode:", self.sweep_mode)
        form_model.addRow("LHS Samples:", self.lhs_samples)
        layout.addWidget(grp_model)

        self.sweep_mode.currentIndexChanged.connect(self._on_change)

        # Geometry
        grp_geo = QGroupBox("Cell Geometry")
        form_geo = QFormLayout(grp_geo)
        self.cell_width = QDoubleSpinBox()
        self.cell_width.setRange(1, 500)
        self.cell_width.setValue(67.56)
        self.cell_width.setDecimals(2)
        self.cell_width.setSuffix(" mm")
        self.cell_height = QDoubleSpinBox()
        self.cell_height.setRange(1, 500)
        self.cell_height.setValue(78.85)
        self.cell_height.setDecimals(2)
        self.cell_height.setSuffix(" mm")
        self.target_height = QDoubleSpinBox()
        self.target_height.setRange(0, 100)
        self.target_height.setValue(4.8)
        self.target_height.setDecimals(2)
        self.target_height.setSuffix(" mm")
        self.target_height.setSpecialValueText("Auto")
        self.height_tol = QDoubleSpinBox()
        self.height_tol.setRange(0, 5)
        self.height_tol.setValue(0.4)
        self.height_tol.setDecimals(2)
        self.height_tol.setSuffix(" mm")
        self.n_layers = QSpinBox()
        self.n_layers.setRange(1, 100)
        self.n_layers.setValue(20)
        self.flat_ratio = QDoubleSpinBox()
        self.flat_ratio.setRange(0.1, 5.0)
        self.flat_ratio.setValue(1.3)
        self.flat_ratio.setDecimals(2)
        self.flat_ratio.setSingleStep(0.1)
        form_geo.addRow("Cell Width:", self.cell_width)
        form_geo.addRow("Cell Height:", self.cell_height)
        form_geo.addRow("Target Height:", self.target_height)
        form_geo.addRow("Height Tolerance:", self.height_tol)
        form_geo.addRow("Layers (n_winds/UC):", self.n_layers)
        form_geo.addRow("Flat Ratio (wound):", self.flat_ratio)
        layout.addWidget(grp_geo)

        # Layer thickness
        grp_thick = QGroupBox("Layer Thickness (mm)")
        form_thick = QFormLayout(grp_thick)
        self.thick_inputs = {}
        defaults = {
            "al_cc": 0.008, "cathode": 0.0807, "separator": 0.0243,
            "anode": 0.0888, "cu_cc": 0.008, "pouch": 0.153, "buffer": 0.200,
        }
        labels = {
            "al_cc": "Al CC", "cathode": "Cathode", "separator": "Separator",
            "anode": "Anode", "cu_cc": "Cu CC", "pouch": "Pouch", "buffer": "Elyte Buffer",
        }
        for key, val in defaults.items():
            ri = RangeInput(val)
            ri.value_changed.connect(self._on_change)
            self.thick_inputs[key] = ri
            form_thick.addRow(f"{labels[key]}:", ri)
        layout.addWidget(grp_thick)

        # Capacity estimation
        grp_cap = QGroupBox("Capacity Estimation")
        form_cap = QFormLayout(grp_cap)
        self.cathode_sp_cap = QDoubleSpinBox()
        self.cathode_sp_cap.setRange(50, 500)
        self.cathode_sp_cap.setValue(200)
        self.cathode_sp_cap.setSuffix(" mAh/g")
        self.cathode_density = QDoubleSpinBox()
        self.cathode_density.setRange(0.5, 10)
        self.cathode_density.setValue(3.00)
        self.cathode_density.setDecimals(2)
        self.cathode_density.setSuffix(" g/cm3")
        self.anode_sp_cap = QDoubleSpinBox()
        self.anode_sp_cap.setRange(50, 1000)
        self.anode_sp_cap.setValue(350)
        self.anode_sp_cap.setSuffix(" mAh/g")
        self.anode_density = QDoubleSpinBox()
        self.anode_density.setRange(0.5, 10)
        self.anode_density.setValue(1.60)
        self.anode_density.setDecimals(2)
        self.anode_density.setSuffix(" g/cm3")
        self.loading = QDoubleSpinBox()
        self.loading.setRange(0.1, 1.0)
        self.loading.setValue(0.95)
        self.loading.setDecimals(2)
        self.loading.setSingleStep(0.05)
        self.nominal_voltage = QDoubleSpinBox()
        self.nominal_voltage.setRange(2.0, 5.0)
        self.nominal_voltage.setValue(3.7)
        self.nominal_voltage.setDecimals(1)
        self.nominal_voltage.setSuffix(" V")
        form_cap.addRow("Cathode Sp. Cap.:", self.cathode_sp_cap)
        form_cap.addRow("Cathode Density:", self.cathode_density)
        form_cap.addRow("Anode Sp. Cap.:", self.anode_sp_cap)
        form_cap.addRow("Anode Density:", self.anode_density)
        form_cap.addRow("Active Loading:", self.loading)
        form_cap.addRow("Nominal Voltage:", self.nominal_voltage)
        layout.addWidget(grp_cap)

        # Output
        grp_out = QGroupBox("Output")
        form_out = QFormLayout(grp_out)
        out_row = QHBoxLayout()
        self.output_dir = QLineEdit(str(Path.home() / "Desktop" / "battery_output"))
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse)
        out_row.addWidget(self.output_dir)
        out_row.addWidget(self.browse_btn)
        form_out.addRow("Directory:", out_row)
        self.output_prefix = QLineEdit("battery")
        form_out.addRow("Prefix:", self.output_prefix)
        layout.addWidget(grp_out)

        # Preview + Generate
        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: #88ccff; font-size: 12px; padding: 4px;")
        layout.addWidget(self.preview_label)

        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.setStyleSheet(
            "QPushButton { background-color: #2d6a4f; color: white; font-size: 14px; "
            "font-weight: bold; border-radius: 6px; } "
            "QPushButton:hover { background-color: #40916c; }"
        )
        layout.addWidget(self.generate_btn)
        layout.addStretch()

        # Connect signals
        for w in [self.model_type, self.tier, self.mode, self.elform]:
            w.currentIndexChanged.connect(self._on_change)
        for w in [self.cell_width, self.cell_height, self.target_height, self.flat_ratio,
                  self.height_tol, self.cathode_sp_cap, self.cathode_density, self.anode_sp_cap,
                  self.anode_density, self.loading, self.nominal_voltage]:
            w.valueChanged.connect(self._on_change)
        self.n_layers.valueChanged.connect(self._on_change)

        self._on_change()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            self.output_dir.setText(d)

    def _get_sweep_mode(self):
        return "lhs" if self.sweep_mode.currentIndex() == 1 else "full"

    def _on_change(self, *args):
        specs = {k: ri.get_spec() for k, ri in self.thick_inputs.items()}
        mode = self._get_sweep_mode()
        n_lhs = self.lhs_samples.value()
        combos = SweepEngine.expand_ranges(specs, mode=mode, n_samples=n_lhs)
        n_combos = len(combos)

        cfg = self._make_base_config()
        n = CapacityCalculator.compute_n_layers(cfg)
        cap = CapacityCalculator.compute_capacity_mah(cfg)
        ed = CapacityCalculator.compute_energy_density(cfg)
        actual_h = CapacityCalculator.compute_actual_height(cfg)

        target_h = self.target_height.value()
        tol = self.height_tol.value()
        text = (f"Layers: {n} | Actual H: {actual_h:.3f}mm | "
                f"Capacity: {cap:.1f} mAh | E.Density: {ed:.1f} Wh/kg")
        if target_h > 0 and tol > 0:
            h_diff = abs(actual_h - target_h)
            if h_diff <= tol:
                text += f"\nHeight OK (target {target_h:.2f} +/-{tol:.2f}mm, diff {h_diff:.3f}mm)"
            else:
                text += f"\nHeight OUT OF RANGE (target {target_h:.2f} +/-{tol:.2f}mm, diff {h_diff:.3f}mm)"
        if n_combos > 1:
            # Compute capacity range across all sweep combos
            caps = []
            heights = []
            for combo in combos:
                sweep_cfg = CellConfig(
                    model_type=cfg.model_type, tier=cfg.tier, mode=cfg.mode,
                    cell_width=cfg.cell_width, cell_height=cfg.cell_height,
                    n_winds=cfg.n_winds if hasattr(cfg, 'n_winds') else 20,
                    n_unit_cells=cfg.n_unit_cells if hasattr(cfg, 'n_unit_cells') else 20,
                    thickness=ThicknessSet(**combo),
                    cathode_sp_cap=cfg.cathode_sp_cap, cathode_density=cfg.cathode_density,
                    anode_sp_cap=cfg.anode_sp_cap, anode_density=cfg.anode_density,
                    loading=cfg.loading, nominal_voltage=cfg.nominal_voltage,
                )
                caps.append(CapacityCalculator.compute_capacity_mah(sweep_cfg))
                heights.append(CapacityCalculator.compute_actual_height(sweep_cfg))
            text += (f"\nSweep: {n_combos} combos | "
                     f"Cap: {min(caps):.0f}~{max(caps):.0f} mAh | "
                     f"H: {min(heights):.3f}~{max(heights):.3f}mm")
        self.preview_label.setText(text)
        self.config_changed.emit()

    def _make_base_config(self) -> CellConfig:
        specs = {k: ri.get_spec() for k, ri in self.thick_inputs.items()}
        t = ThicknessSet(
            al_cc=specs["al_cc"].value if not specs["al_cc"].is_range else (specs["al_cc"].range_min + specs["al_cc"].range_max) / 2,
            cathode=specs["cathode"].value if not specs["cathode"].is_range else (specs["cathode"].range_min + specs["cathode"].range_max) / 2,
            separator=specs["separator"].value if not specs["separator"].is_range else (specs["separator"].range_min + specs["separator"].range_max) / 2,
            anode=specs["anode"].value if not specs["anode"].is_range else (specs["anode"].range_min + specs["anode"].range_max) / 2,
            cu_cc=specs["cu_cc"].value if not specs["cu_cc"].is_range else (specs["cu_cc"].range_min + specs["cu_cc"].range_max) / 2,
            pouch=specs["pouch"].value if not specs["pouch"].is_range else (specs["pouch"].range_min + specs["pouch"].range_max) / 2,
            buffer=specs["buffer"].value if not specs["buffer"].is_range else (specs["buffer"].range_min + specs["buffer"].range_max) / 2,
        )
        return CellConfig(
            model_type=self.model_type.currentText(),
            tier=float(self.tier.currentText()),
            mode=self.mode.currentText(),
            solid_electrode=self.solid_electrode.isChecked(),
            solid_elform=int(self.elform.currentText()[0]),
            cell_width=self.cell_width.value(),
            cell_height=self.cell_height.value(),
            target_height=self.target_height.value(),
            n_winds=self.n_layers.value(),
            n_unit_cells=self.n_layers.value(),
            flat_ratio=self.flat_ratio.value(),
            thickness=t,
            cathode_sp_cap=self.cathode_sp_cap.value(),
            cathode_density=self.cathode_density.value(),
            anode_sp_cap=self.anode_sp_cap.value(),
            anode_density=self.anode_density.value(),
            loading=self.loading.value(),
            nominal_voltage=self.nominal_voltage.value(),
        )

    def collect_configs(self) -> list:
        """Return list of (CellConfig, yaml_path) for all sweep combinations."""
        specs = {k: ri.get_spec() for k, ri in self.thick_inputs.items()}
        mode = self._get_sweep_mode()
        n_lhs = self.lhs_samples.value()
        combos = SweepEngine.expand_ranges(specs, mode=mode, n_samples=n_lhs)
        base = self._make_base_config()
        output_dir = Path(self.output_dir.text())
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = self.output_prefix.text() or "battery"

        configs = []
        for i, combo in enumerate(combos):
            cfg = CellConfig(
                model_type=base.model_type,
                tier=base.tier,
                mode=base.mode,
                solid_electrode=base.solid_electrode,
                solid_elform=base.solid_elform,
                cell_width=base.cell_width,
                cell_height=base.cell_height,
                target_height=base.target_height,
                n_winds=base.n_winds,
                n_unit_cells=base.n_unit_cells,
                flat_ratio=base.flat_ratio,
                thickness=ThicknessSet(**combo),
                cathode_sp_cap=base.cathode_sp_cap,
                cathode_density=base.cathode_density,
                anode_sp_cap=base.anode_sp_cap,
                anode_density=base.anode_density,
                loading=base.loading,
                nominal_voltage=base.nominal_voltage,
                soc=1.0,
                nmc_cte=0.04,
                graphite_cte=0.10,
                output_dir=str(output_dir),
                output_prefix=prefix,
            )
            # Build filename label
            if len(combos) == 1:
                fname = f"{prefix}_{base.model_type}"
            else:
                parts = []
                for k, v in combo.items():
                    parts.append(f"{k}{v:.4f}")
                fname = f"{prefix}_{i:04d}_{'_'.join(parts)}"
                if len(fname) > 80:
                    fname = f"{prefix}_{i:04d}"

            yaml_path = YamlGenerator.generate(cfg, output_dir, fname)
            configs.append((cfg, yaml_path))
        return configs


# ═══════════════════════════════════════════════════════════════
# Results Panel
# ═══════════════════════════════════════════════════════════════

class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Results table
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "File", "Type", "Tier", "Layers", "Target H",
            "Actual H", "Cap (mAh)", "E.D. (Wh/kg)", "Status"
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 9):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, stretch=3)

        # Summary
        grp_summary = QGroupBox("Summary")
        sum_layout = QVBoxLayout(grp_summary)
        self.summary_label = QLabel("No results yet.")
        self.summary_label.setStyleSheet("font-size: 13px; padding: 4px;")
        self.summary_label.setWordWrap(True)
        sum_layout.addWidget(self.summary_label)
        layout.addWidget(grp_summary)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumBlockCount(5000)
        self.log_area.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_area, stretch=1)

        self._results = []

    def clear(self):
        self.table.setRowCount(0)
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.summary_label.setText("Generating...")
        self._results = []

    def add_result(self, r: SweepResult):
        self._results.append(r)
        row = self.table.rowCount()
        self.table.insertRow(row)

        items = [
            r.filename, r.model_type, f"{r.tier:.0f}", str(r.n_layers),
            f"{r.target_h:.3f}", f"{r.actual_h:.3f}",
            f"{r.capacity_mah:.1f}", f"{r.energy_density:.1f}", r.status
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if r.status != "OK":
                item.setForeground(QColor(255, 120, 120))
            self.table.setItem(row, col, item)

        self.table.scrollToBottom()

    def update_summary(self):
        if not self._results:
            self.summary_label.setText("No results.")
            return
        caps = [r.capacity_mah for r in self._results if r.status == "OK"]
        eds = [r.energy_density for r in self._results if r.status == "OK"]
        ok = len(caps)
        total = len(self._results)

        if not caps:
            self.summary_label.setText(f"0/{total} succeeded.")
            return

        text = (f"Results: {ok}/{total} OK\n"
                f"Capacity: {min(caps):.1f} ~ {max(caps):.1f} mAh "
                f"(avg {sum(caps)/len(caps):.1f})\n"
                f"Energy Density: {min(eds):.1f} ~ {max(eds):.1f} Wh/kg "
                f"(avg {sum(eds)/len(eds):.1f})")
        self.summary_label.setText(text)


# ═══════════════════════════════════════════════════════════════
# Main Window
# ═══════════════════════════════════════════════════════════════

class BatteryModelGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KooRemapper - Battery Cell Modeler")
        self.resize(1200, 800)

        # Find KooRemapper.exe
        script_dir = Path(__file__).parent
        self.exe_path = script_dir.parent / "build" / "bin" / "Release" / "KooRemapper.exe"
        if not self.exe_path.exists():
            self.exe_path = script_dir.parent / "build" / "bin" / "Debug" / "KooRemapper.exe"

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Input (in scroll area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.input_panel = InputPanel()
        scroll.setWidget(self.input_panel)
        scroll.setMinimumWidth(420)
        scroll.setMaximumWidth(520)

        # Right: Results
        self.results_panel = ResultsPanel()

        splitter.addWidget(scroll)
        splitter.addWidget(self.results_panel)
        splitter.setSizes([420, 780])
        main_layout.addWidget(splitter)

        # Connect
        self.input_panel.generate_btn.clicked.connect(self._on_generate)
        self.worker = None

    def _on_generate(self):
        if not self.exe_path.exists():
            QMessageBox.warning(self, "Error",
                f"KooRemapper.exe not found at:\n{self.exe_path}\n\n"
                "Please build the project first.")
            return

        configs = self.input_panel.collect_configs()
        if not configs:
            QMessageBox.warning(self, "Error", "No configurations to generate.")
            return

        n = len(configs)
        if n > 50:
            reply = QMessageBox.question(self, "Confirm",
                f"This will generate {n} models. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.results_panel.clear()
        self.results_panel.progress_bar.setMaximum(n)
        self.input_panel.generate_btn.setEnabled(False)
        self.input_panel.generate_btn.setText("Generating...")

        output_dir = Path(self.input_panel.output_dir.text())
        self.worker = GeneratorWorker(configs, output_dir, self.exe_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.result_ready.connect(self._on_result)
        self.worker.log_message.connect(self._on_log)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, current, total):
        self.results_panel.progress_bar.setValue(current)

    def _on_result(self, result):
        self.results_panel.add_result(result)

    def _on_log(self, msg):
        self.results_panel.log_area.appendPlainText(msg)

    def _on_error(self, msg):
        QMessageBox.warning(self, "Generation Error", msg)

    def _on_finished(self):
        self.results_panel.update_summary()
        self.input_panel.generate_btn.setEnabled(True)
        self.input_panel.generate_btn.setText("Generate")


# ═══════════════════════════════════════════════════════════════
# Dark theme
# ═══════════════════════════════════════════════════════════════

def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(208, 208, 208))
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(208, 208, 208))
    palette.setColor(QPalette.ColorRole.Text, QColor(208, 208, 208))
    palette.setColor(QPalette.ColorRole.Button, QColor(60, 60, 63))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(208, 208, 208))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, QColor(100, 180, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(38, 79, 120))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128, 128, 128))
    app.setPalette(palette)

    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #555;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 14px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }
        QTableWidget {
            gridline-color: #444;
            font-size: 12px;
        }
        QHeaderView::section {
            background-color: #3a3a3a;
            padding: 4px;
            border: 1px solid #555;
            font-weight: bold;
        }
        QProgressBar {
            border: 1px solid #555;
            border-radius: 3px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #2d6a4f;
        }
    """)


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = BatteryModelGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
