**English** | [Türkçe](README.tr.md)

# Lythos Kinematic

Rock slope kinematics and stability, driven from your browser. Two steps, one workflow:

1. **Kinematic screening** — the Markland test on a stereonet, pole density and a Monte
   Carlo probability of failure establish *which failure mechanism is possible*.
2. **Limit equilibrium** — for the mechanism found critical, compute the *factor of
   safety, the required support and the bolt design*.

The two steps are bridged: the most critical discontinuity or intersection found during
screening is written into the limit-equilibrium inputs with one click. The whole
application — every label, result text, plot and PDF report — is bilingual in **Turkish
and English**, switchable at runtime.

The interface is a small HTTP server on your own machine, driven from a browser. That
keeps the program usable over a remote session or inside a container, where a desktop
toolkit would need a display it does not have, and it costs no dependency beyond the
standard library.

> This is the sibling of [LythosFEA](https://github.com/hdaltuntas/lythos) and follows
> the same architecture. It merges two formerly separate desktop programs,
> **SlopeKinematics** and **Kinematix**; see [Background](#background).

## Screenshots

| Kinematic screening | Bolt spacing × length matrix |
|---|---|
| ![Kinematic screening](assets/screening.png) | ![Bolt matrix](assets/bolts.png) |

| Probabilistic analysis | Wedge analysis | English interface, dark theme |
|---|---|---|
| ![Probability](assets/probability.png) | ![Wedge](assets/wedge.png) | ![Dark theme](assets/english_dark.png) |

## Install & run

```bash
pip install lythoskinematic
lythos-kinematic                 # opens the interface in your browser
```

From a clone, with nothing installed but the scientific stack:

```bash
pip install numpy scipy matplotlib reportlab
python main.py
```

Python 3.10+ is required.

## Command line

```bash
lythos-kinematic                          # web interface (the default)
lythos-kinematic web --port 9000 --lang EN --no-browser
lythos-kinematic example -o inputs.json   # a starter input file
lythos-kinematic screen inputs.json -o screening.pdf
lythos-kinematic run inputs.json --mode wedge -o wedge.pdf
```

`screen` and `run` read the same JSON the interface saves, so a case set up in the
browser can be re-run unattended.

## What it computes

### Kinematic screening
- **Kinematic tests:** planar sliding, wedge sliding (Markland), flexural toppling
  (Goodman & Bray)
- **Stereonet:** equal-area (Schmidt) lower-hemisphere projection, pole density contour
  (Kamb counting cone), critical zone sweep, friction / sliding limit cone
- **Monte Carlo:** overall and component-wise probability of failure accounting for
  discontinuity orientation uncertainty; runs on a background thread, the page stays live
- **PDF report:** checks, probabilities and the stereonet in one file

### Limit equilibrium
- **Wedge (Swedge):** tetrahedral wedge geometry, Hoek & Bray vector limit equilibrium,
  3D view and stereonet
- **Planar (RocPlane):** tension crack, water pressure, seismic load, 2D section
- **Toppling (RocTopple):** Goodman & Bray block toppling, water + seismic + toe anchor
- **Support design:** force required for a target FS, a clickable bolt spacing × length
  matrix, and a capacity/FS check for the design you pick
- **PDF report:** project data, input tables, figures, force-balance tables

### The bridge
**"→ Send critical result to limit equilibrium"** transfers the most critical component:

| Screening mode | Transferred inputs |
|---|---|
| Planar | sliding plane ψp, slope face ψf, friction angle φ |
| Wedge | Joint 1 and Joint 2 dip/dip dir, slope face dip/dip dir, φ |
| Toppling | discontinuity dip ψd, slope face ψf, φ |

## Layout

```
main.py                    run from a clone without installing
lythoskinematic/
  cli.py                   command line (web · screen · run · example)
  i18n.py                  language switch; bilingual text helper T("tr", "en")
  forms.py                 input schema and readers — one definition per field
  stereonet.py             shared lower-hemisphere projection (no extra deps)
  render.py                figures as PNG, for the browser and the report alike
  theme.py                 plot palette
  kinematics/              screening core — independent of the interface
    engine.py              Markland criteria + Monte Carlo
    plots.py               screening stereonet
    htmlreport.py          HTML report bodies
    report.py              screening PDF report
    i18n.py                TR/EN strings
  rockslope/               limit-equilibrium core — independent of the interface
    core.py wedge.py planar.py toppling.py bolts.py report.py style.py text.py
  web/
    server.py              HTTP routes (standard library only)
    session.py             the one working session: analyses, figures, reports
    strings.py             interface text, served to the page
    static/                index.html · style.css · app.js
tests/                     pytest suite
```

Forms are generated from `forms.py`: a field's key, label, unit, range and default are
written once, in Python, and the page renders whatever the server sends. There is no
second copy of the labels in JavaScript and nothing to keep in step by hand — switching
language simply re-fetches the schema.

## Background

Lythos Kinematic began as two desktop programs, **SlopeKinematics** (kinematics and
probability, PyQt5) and **Kinematix** (limit equilibrium, bolting and reporting,
PySide6). Merging them required three changes worth recording:

1. **One interface.** Two Qt bindings cannot share a process, and a desktop toolkit needs
   a display. Both interfaces were replaced by this browser-driven one, which also brought
   the two programs' workflows together behind a single set of inputs.
2. **mplstereonet removed.** Stereonet drawing now comes from one shared implementation in
   `stereonet.py` (equal-area/equal-angle projection, great and small circles, pole density
   via the Kamb counting cone). Both modules plot on exactly the same geometry, and a
   dependency that fails to build on current Python versions is gone.
3. **One reporting path.** Screening reports used to be printed through Qt; everything now
   goes through the same reportlab template as the limit-equilibrium report, so both
   modules produce the same document, and no display is needed to make a PDF.

While unifying the projection, **a radius normalisation bug in the equal-area projection
was fixed**: horizontal lines (plunge = 0) landed at 70.7 % of the radius instead of on
the primitive circle, so all data was squeezed into the inner part of the net. The fix is
pinned by `tests/test_stereonet.py`.

## Validation

```bash
pip install -e ".[dev]"
pytest
```

The cores are pinned against closed-form solutions:

- **wedge** — matches the Hoek & Bray closed-form short solution exactly
  (dry 1.696 / flooded 1.065)
- **planar** — c = 0, dry: tanφ/tanψp
- **toppling** — Wyllie & Mah Chapter 9 example (block heights, failure modes,
  limit-equilibrium φ ≈ 38°)
- **kinematics** — the intersection line is cross-checked against the independent vector
  implementation in the limit-equilibrium core; with zero uncertainty the Monte Carlo
  result must reduce to the deterministic 0/100 answer
- **stereonet** — projection radii against the analytical Schmidt/Wulff values, poles
  against being perpendicular to the dip vector
- **i18n** — every summary follows the language, the fixed-width label column stays
  aligned in both, the numbers never change, and internal keys are never translated
- **web** — the schema covers every field, the session's analyses reproduce the validated
  results, background jobs finish without deadlocking the state poll, and the HTTP routes
  return PNG figures, PDF reports and plain error messages rather than stack traces

## License

MIT — see [LICENSE](LICENSE).
