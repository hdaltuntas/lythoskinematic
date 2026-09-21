**English** | [Türkçe](README.tr.md)

# Lythos Suite v1.0

A geotechnical analysis application suite. Its first module, **Lythos Kinematic**,
brings rock slope kinematics and stability into a single workflow:

1. **Kinematic Screening** — Markland test, stereonet and Monte Carlo probabilistic
   analysis establish *which failure mechanism is kinematically possible*.
2. **Limit Equilibrium** — for the mechanism found critical, compute the *factor of
   safety, the required support and the bolt design*.

The two steps are bridged: the most critical discontinuity or intersection found
during screening is transferred into the limit-equilibrium inputs with one click.

> This application merges two formerly separate programs: **SlopeKinematics**
> (kinematics + probability) and **Kinematix** (limit equilibrium + bolting +
> reporting). See [Merge notes](#merge-notes).

## Screenshots

| Kinematic screening (light theme) | Limit equilibrium (dark theme) |
|---|---|
| ![Kinematic screening](assets/screenshot_screening.png) | ![Limit equilibrium](assets/screenshot_equilibrium_dark.png) |

| Probabilistic analysis report |
|---|
| ![Probabilistic analysis](assets/screenshot_probability.png) |

## Install & run

```bash
pip install -r requirements.txt
python lythos_suite.py          # or:  python -m lythos
```

Python 3.9+ is required. The UI is built on PySide6 (LGPL); `mplstereonet` and
`PyQt5` are **no longer needed** (see below).

## Module: Lythos Kinematic

### 1 · Kinematic Screening
- **Kinematic tests:** planar sliding, wedge sliding (Markland), flexural toppling
  (Goodman & Bray)
- **Stereonet:** equal-area (Schmidt) lower-hemisphere projection, pole density
  contour (Kamb counting cone), critical zone sweep, friction / sliding limit cone
- **Monte Carlo:** overall and component-wise Probability of Failure (PoF) accounting
  for discontinuity orientation uncertainty (dip and dip direction std. dev.); runs
  on a background thread, the UI never freezes
- **PDF report:** kinematic checks + probabilistic analysis + stereonet in one file
- **Turkish / English** interface

### 2 · Limit Equilibrium
- **Wedge (Swedge):** tetrahedral wedge geometry, Hoek & Bray vector limit
  equilibrium, 3D visualisation, stereonet
- **Planar (RocPlane):** tension crack, water pressure, seismic load, 2D section
- **Toppling (RocTopple):** Goodman & Bray block toppling, water + seismic + toe anchor
- **Support design:** support force required for a target FS, bolt spacing × length
  recommendation matrix, capacity/FS check for the chosen design
- **PDF report:** project data, input tables, figures, force-balance tables

### The bridge: screening → limit equilibrium
The **"→ Send critical result to Limit Equilibrium"** button writes the most critical
component into the limit-equilibrium inputs and runs the analysis:

| Screening mode | Transferred inputs |
|---|---|
| Planar | sliding plane ψp, slope face ψf, friction angle φ |
| Wedge | Joint 1 and Joint 2 dip/dip dir, slope face dip/dip dir, φ |
| Toppling | discontinuity dip ψd, slope face ψf, φ |

## Shortcuts

In the limit-equilibrium panel: `F5` analyse · `F6` required support · `F7` bolt
recommendation · `F8` bolt check · `Ctrl+P` PDF · `Ctrl+S` / `Ctrl+O` save / load
inputs. Suite-wide: `F1` about.

## Layout

```
lythos_suite.py            entry point
lythos/
  app.py                   Lythos Suite shell (module tabs, theme, language, persistence)
  theme.py                 shared light/dark theme (QSS + matplotlib palette)
  stereonet.py             shared lower-hemisphere stereonet projection (no extra deps)
  kinematics/              kinematic screening core
    engine.py              Markland criteria + Monte Carlo (independent of Qt)
    plots.py               screening stereonet
    htmlreport.py          HTML report bodies (shared by screen and PDF)
    i18n.py                TR/EN strings
  rockslope/               limit-equilibrium core (independent of Qt)
    core.py wedge.py planar.py toppling.py bolts.py report.py style.py
  ui/                      PySide6 interface
    screening.py           kinematic screening panel
    equilibrium.py         limit-equilibrium panel
    kinematic.py           Lythos Kinematic module (both panels + the bridge)
    widgets.py qt.py       shared widgets, Qt binding
tests/                     pytest validation suite
```

To add a module, append a `ModuleSpec` to `MODULES` in `lythos/app.py`; if the module
provides `state()`, `apply_state()`, `set_language()`, `apply_theme()` and
`shutdown()`, the shell handles the rest.

## Merge notes

Two technical changes were required by the merge:

1. **One Qt binding.** SlopeKinematics used PyQt5, Kinematix used PySide6, and two Qt
   builds cannot live in one process. The screening UI was ported to PySide6.
2. **mplstereonet removed.** Stereonet drawing now comes from a single shared
   implementation in `lythos/stereonet.py` (equal-area/equal-angle projection, great
   and small circles, pole density via the Kamb counting cone). Both modules therefore
   plot on exactly the same geometry, and a dependency that fails to build on current
   Python versions is gone.

While unifying the projection, **a radius normalisation bug in the equal-area
projection was fixed**: horizontal lines (plunge = 0) landed at 70.7 % of the radius
instead of on the primitive circle, so all data was squeezed into the inner part of
the net. The fix is pinned by `tests/test_stereonet.py`.

## Validation

The computation cores are pinned against closed-form solutions with pytest:

- **wedge** — matches the Hoek & Bray closed-form short solution exactly
  (dry 1.696 / flooded 1.065)
- **planar** — c = 0, dry: tanφ/tanψp
- **toppling** — Wyllie & Mah Chapter 9 example (block heights, failure modes,
  limit-equilibrium φ ≈ 38°)
- **kinematics** — the intersection line is cross-checked against the independent
  vector implementation in the limit-equilibrium core; with zero uncertainty the
  Monte Carlo result must reduce to the deterministic 0/100 answer
- **stereonet** — projection radii are checked against the analytical Schmidt/Wulff
  values, and poles against being perpendicular to the dip vector

```bash
pip install -r requirements-dev.txt
pytest
```

## Single-file executable (optional)

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Lythos Suite" --collect-all reportlab lythos_suite.py
```

On Windows the report uses Arial (`C:\Windows\Fonts`) for Turkish characters; on
Linux, DejaVu Sans.

## License

MIT — see [LICENSE](LICENSE). PySide6 is LGPL; no additional license is required for
in-house distribution.

## Troubleshooting (Windows)

**`ImportError: DLL load failed while importing QtCore`** → two different Qt installs
loaded at once, or mismatched PySide6/shiboken6 versions.

1. Diagnose: `python check_env.py` (PySide6 and shiboken6 versions must match;
   PyQt5/PyQt6 present is a common conflict source).
2. Clean reinstall: `pip uninstall -y PySide6 PySide6-Essentials PySide6-Addons shiboken6`
   → `pip install PySide6`
3. Most robust: a separate virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python lythos_suite.py
   ```
4. If using Anaconda: `conda create -n lythos python=3.11` → `conda activate lythos`
   → `pip install -r requirements.txt`.
   (Avoid mixing the PyQt5/qt packages in the Anaconda base environment with
   pip-installed PySide6.)
5. If it still fails, install the Microsoft Visual C++ 2015–2022 Redistributable (x64).
