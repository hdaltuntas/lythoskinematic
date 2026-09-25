**English** | [Türkçe](CHANGELOG.tr.md)

# Changelog

Notable changes, newest first. Versions follow [semantic versioning](https://semver.org).

## Unreleased

- The licence changes from MIT to the GNU Affero General Public License, version 3
  (`AGPL-3.0-only`). Versions already published keep the MIT licence they were released under.

## 0.1.0 — 2026-09-22

First release. [PyPI](https://pypi.org/project/lythoskinematic/0.1.0/)

Lythos Kinematic merges two formerly separate desktop programs — **SlopeKinematics**
(kinematics and probability, PyQt5) and **Kinematix** (limit equilibrium, bolting and
reporting, PySide6) — into one browser-driven application, and continues their history.

### Added

- **Kinematic screening** — the Markland test on an equal-area stereonet, pole density
  contouring with the Kamb counting cone, a critical-zone sweep, and a Monte Carlo
  probability of failure that accounts for discontinuity orientation uncertainty.
- **Limit equilibrium** — wedge (Hoek & Bray vector method), planar sliding, and
  Goodman & Bray block toppling; the support force required for a target FS, a clickable
  bolt spacing × length matrix, and a capacity/FS check for the chosen design.
- **The bridge** — the most critical discontinuity or intersection found during screening
  is written into the limit-equilibrium inputs with one click.
- **Web interface** — a local HTTP server on the standard library alone, so it works over
  a remote session or inside a container where a desktop toolkit would need a display.
  Figures are rendered server-side; the same figures go into the PDFs.
- **Bilingual throughout** — Turkish and English for labels, result texts, warnings, error
  messages, plot labels and the PDF reports, switchable at runtime. Switching rebuilds the
  forms without losing the inputs and never changes a number.
- **PDF reports** — one reportlab template for both modules: project data, input tables,
  figures, force-balance tables, references and a signature block.
- **Command line** — `web`, `screen`, `run`, `example`. `screen` and `run` read the same
  JSON the interface saves, so a case set up in the browser can be re-run unattended.
- **Input schema** (`forms.py`) — a field's key, label, unit, range and default are
  written once, in Python; the page renders whatever the server sends, so there is no
  second copy of the labels in JavaScript.
- `tools/upload_to_pypi.py` — builds and uploads a release, refuses a version already on
  PyPI, and explains a rejected upload.

### Changed, relative to the predecessor programs

- **One interface.** Two Qt bindings cannot share a process, and a desktop toolkit needs a
  display. Both desktop interfaces were replaced by the browser-driven one, which also
  brought the two programs' workflows together behind a single set of inputs.
- **`mplstereonet` removed.** Stereonet drawing now comes from one shared implementation
  in `stereonet.py` (equal-area/equal-angle projection, great and small circles, pole
  density via the Kamb counting cone). Both modules plot on exactly the same geometry, and
  a dependency that fails to build on current Python versions is gone.
- **One reporting path.** Screening reports used to be printed through Qt; everything now
  goes through the same reportlab template, so no display is needed to make a PDF.
- **PySide6 is no longer a dependency.** The package needs only NumPy, SciPy, Matplotlib
  and reportlab.

### Fixed

- **Radius normalisation in the equal-area projection.** Horizontal lines (plunge = 0)
  landed at 70.7 % of the radius instead of on the primitive circle, so all data was
  squeezed into the inner part of the net. Present in Kinematix's wedge stereonet; pinned
  by `tests/test_stereonet.py`.

### Validation

111 tests. The computation cores are pinned against closed-form solutions: wedge 1.696 dry
/ 1.065 flooded against the Hoek & Bray short solution, planar tanφ/tanψp for c = 0 dry,
and toppling against the Wyllie & Mah Chapter 9 example. The kinematic intersection line
is cross-checked against the independent vector implementation in the limit-equilibrium
core, and with zero uncertainty the Monte Carlo result reduces to the deterministic 0/100
answer.

### Known issues

- Piping command-line output into a command that closes the pipe early (`lythos-kinematic
  screen inputs.json | head`) ends in a `BrokenPipeError` traceback instead of exiting
  quietly.
