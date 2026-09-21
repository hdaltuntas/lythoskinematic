"""Komut satırı arayüzü."""

from __future__ import annotations

import argparse
import sys

from . import APP_NAME, __version__


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="lythos-kinematic",
        description="Rock slope kinematics and stability: Markland screening, "
                    "Monte Carlo probability and limit-equilibrium analysis.")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command")

    web = sub.add_parser("web", help="start the interface in a browser")
    web.add_argument("--port", type=int, default=8778)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--lang", default="TR", choices=["TR", "EN"])
    web.add_argument("--no-browser", action="store_true")

    screen = sub.add_parser("screen", help="run a kinematic screening from an input file")
    screen.add_argument("inputs", help="path to a .json input file")
    screen.add_argument("-o", "--out", default=None, help="write a PDF report here")
    screen.add_argument("--lang", default="TR", choices=["TR", "EN"])

    run = sub.add_parser("run", help="run a limit-equilibrium analysis from an input file")
    run.add_argument("inputs", help="path to a .json input file")
    run.add_argument("--mode", default="wedge", choices=["wedge", "planar", "toppling"])
    run.add_argument("-o", "--out", default=None, help="write a PDF report here")
    run.add_argument("--lang", default="TR", choices=["TR", "EN"])

    example = sub.add_parser("example", help="write a starter input file")
    example.add_argument("-o", "--out", default="lythos_inputs.json")

    args = parser.parse_args(argv)
    command = args.command or "web"

    if command == "web":
        from .web.server import serve
        serve(host=getattr(args, "host", "127.0.0.1"), port=getattr(args, "port", 8778),
              open_browser=not getattr(args, "no_browser", False),
              lang=getattr(args, "lang", "TR"))
        return 0

    if command == "example":
        import json

        from . import forms
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"format": "lythos-kinematic", "version": 1, **forms.defaults()},
                      fh, indent=2, ensure_ascii=False)
        print(args.out)
        return 0

    import json

    from .i18n import set_language
    from .web.session import Session

    set_language(args.lang)
    with open(args.inputs, encoding="utf-8") as fh:
        values = json.load(fh)
    session = Session()

    if command == "screen":
        result = session.screen(values)
        if not result["ok"]:
            print(result["error"], file=sys.stderr)
            return 1
        payload = result["result"]
        print(f"{payload['mode_label']}: {payload['n_critical']} / {payload['n_items']}")
        for item in payload["items"]:
            print(f"  {item['name']:<16} {item['status']}")
        if args.out:
            import time
            while session.state()["job"] == "running":   # Monte Carlo bitsin
                time.sleep(0.05)
            print(session.report("screening", args.out))
        return 0

    result = session.equilibrium(args.mode, values)
    print(result["summary"])
    if args.out:
        print(session.report("equilibrium", args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
