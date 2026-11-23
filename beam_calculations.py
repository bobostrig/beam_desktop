"""Standalone beam response calculations. Forces are kip, distances inch internally."""
from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np


@dataclass(frozen=True)
class Load:
    kind: Literal["point", "uniform"]
    magnitude: float  # kip or kip/ft
    direction: Literal["Downward", "Upward"]
    position: float = 0.0  # ft, for point load
    start: float = 0.0  # ft, for uniform load
    end: float = 0.0  # ft, for uniform load


@dataclass
class BeamResults:
    x_ft: np.ndarray
    shear_kip: np.ndarray
    moment_kip_ft: np.ndarray
    deflection_in: np.ndarray
    reaction_left_kip: float
    reaction_right_kip: float
    extrema: dict
    bending_stress_ksi: float
    deflection_limit_in: float


def analyze_beam(support: str, span_ft: float, loads: Sequence[Load],
                 E_ksi: float, I_in4: float, S_in3: float,
                 allowable_ksi: float, deflection_limit_in: float | None = None,
                 samples: int = 801) -> BeamResults:
    """Analyze a simply supported or cantilever beam and return signed diagrams."""
    if support not in ("Simply supported", "Cantilever"):
        raise ValueError("Support must be Simply supported or Cantilever")
    if not np.isfinite(span_ft) or span_ft <= 0:
        raise ValueError("Span must be a positive finite value")
    if any(not np.isfinite(v) or v <= 0 for v in (E_ksi, I_in4, S_in3, allowable_ksi)):
        raise ValueError("E, I, S, and allowable stress must be positive and finite")
    if samples < 3:
        raise ValueError("At least 3 samples are required")
    for load in loads:
        if load.kind not in ("point", "uniform") or load.direction not in ("Upward", "Downward"):
            raise ValueError("Unsupported load type or direction")
        if not np.isfinite(load.magnitude) or load.magnitude < 0:
            raise ValueError("Load magnitudes must be finite and nonnegative")
        if load.kind == "point" and not 0 <= load.position <= span_ft:
            raise ValueError("Point loads must be within the beam span")
        if load.kind == "uniform" and not (0 <= load.start < load.end <= span_ft):
            raise ValueError("Uniform load endpoints must satisfy 0 <= start < end <= span")

    sign = lambda load: -1.0 if load.direction == "Downward" else 1.0
    total_force = 0.0
    total_moment_left = 0.0
    for load in loads:
        s = sign(load)
        if load.kind == "point":
            f = s * load.magnitude
            total_force += f
            total_moment_left += f * load.position
        else:
            f = s * load.magnitude * (load.end - load.start)
            total_force += f
            total_moment_left += f * (load.start + load.end) / 2
    if support == "Cantilever":
        ra, rb = -total_force, 0.0
        fixed_moment_kipft = -total_moment_left
    else:
        rb = -total_moment_left / span_ft
        ra = -total_force - rb
        fixed_moment_kipft = 0.0

    x_ft = np.linspace(0.0, span_ft, samples)
    x_in = x_ft * 12.0
    shear = np.full(samples, ra, dtype=float)
    moment_kipin = ra * x_in
    for load in loads:
        s = sign(load)
        if load.kind == "point":
            a = load.position * 12.0
            p = s * load.magnitude
            active = x_in >= a
            shear[active] += p
            moment_kipin[active] += p * (x_in[active] - a)
        else:
            a, b = load.start * 12.0, load.end * 12.0
            w = s * load.magnitude / 12.0
            z = np.clip(x_in - a, 0.0, b - a)
            shear += w * z
            moment_kipin += w * z * (x_in - a - z / 2.0)
    if support == "Cantilever":
        moment_kipin += fixed_moment_kipft * 12.0
    # Integrate curvature twice. For a simple beam, remove the linear drift
    # needed to satisfy zero vertical displacement at both supports.
    curvature = moment_kipin / (E_ksi * I_in4)
    dx = x_in[1] - x_in[0]
    theta = np.zeros(samples)
    v = np.zeros(samples)
    theta[1:] = np.cumsum((curvature[:-1] + curvature[1:]) * 0.5 * dx)
    v[1:] = np.cumsum((theta[:-1] + theta[1:]) * 0.5 * dx)
    if support == "Simply supported":
        v -= (x_in / x_in[-1]) * v[-1]
    moment_kipft = moment_kipin / 12.0
    abs_m = float(np.max(np.abs(moment_kipft)))
    stress = abs_m * 12.0 / S_in3
    limit = deflection_limit_in if deflection_limit_in is not None else span_ft * 12.0 / 360.0
    if not np.isfinite(limit) or limit <= 0:
        raise ValueError("Deflection limit must be a positive finite value")
    series = {"shear": shear, "moment": moment_kipft, "deflection": v}
    extrema = {}
    for name, values in series.items():
        imin, imax = int(np.argmin(values)), int(np.argmax(values))
        extrema[name] = {"min": float(values[imin]), "min_x_ft": float(x_ft[imin]),
                         "max": float(values[imax]), "max_x_ft": float(x_ft[imax])}
    return BeamResults(x_ft, shear, moment_kipft, v, ra, rb, extrema,
                       stress, float(limit))
