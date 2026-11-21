#!/usr/bin/env python3
"""Render the plugin locally with live data so it can be checked in a browser.

Usage:
  python3 preview/build.py [--hours 24] [--header top|summary] [--units gw|percent]
                           [--legend yes|no] [--out DIR]

Writes full.html, mashup_halves.html, mashup_vertical.html and mashup_quadrants.html.
The settings flags stand in for the plugin's form fields on trmnl.com.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://trmnl.com/css/latest/plugins.css">
<script src="https://trmnl.com/js/latest/plugins.js"></script>
<style>body{{margin:0}}</style>
</head><body class="environment trmnl">
<div class="screen">{body}</div>
</body></html>"""


def polling_urls(hours):
    """Python twin of src/polling_urls.liquid."""
    now = dt.datetime.now(dt.timezone.utc)
    start = (now - dt.timedelta(hours=hours + 2)).strftime("%Y-%m-%dT%H:00:00Z")
    end = (now + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:00:00Z")
    return [
        f"https://data.elexon.co.uk/bmrs/api/v1/generation/outturn/summary?startTime={start}",
        f"https://api.pvlive.uk/pvlive/api/v4/gsp/0?start={start}&end={end}",
        "https://api.carbonintensity.org.uk/intensity",
    ]


def fetch(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "trmnl-preview"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def render(name, data, settings):
    text = (SRC / f"{name}.liquid").read_text()
    for i, payload in enumerate(data):
        text = re.sub(r"\{\{\s*IDX_%d\s*\|\s*json\s*\}\}" % i, lambda _: json.dumps(payload), text)

    # {{ field | default: 'x' }} -> the chosen setting, or the default.
    def field(m):
        return str(settings.get(m.group(1)) or m.group(2))

    return re.sub(r"\{\{\s*(\w+)\s*\|\s*default:\s*'?([^'}\s]*)'?\s*\}\}", field, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24, choices=[6, 12, 24, 48, 72])
    ap.add_argument("--header", default="top", choices=["top", "summary"])
    ap.add_argument("--units", default="gw", choices=["gw", "percent"])
    ap.add_argument("--legend", default="yes", choices=["yes", "no"])
    ap.add_argument("--out", default=str(ROOT / "preview" / "out"))
    a = ap.parse_args()

    settings = {"hours": a.hours, "header": a.header, "units": a.units, "show_legend": a.legend}
    data = [fetch(u) for u in polling_urls(a.hours)]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    def r(name):
        return render(name, data, settings)

    shared = r("shared")
    (out / "full.html").write_text(PAGE.format(body=shared + r("full")))
    (out / "mashup_halves.html").write_text(PAGE.format(
        body=shared + '<div class="mashup mashup--1Tx1B">'
        + r("half_horizontal")
        + r("half_horizontal").replace("ukgrid-hh", "ukgrid-hh2").replace("ukgrid-chart-hh", "ukgrid-chart-hh2")
        + "</div>"))
    (out / "mashup_vertical.html").write_text(PAGE.format(
        body=shared + '<div class="mashup mashup--1Lx1R">'
        + r("half_vertical")
        + r("quadrant").replace("view--quadrant", "view--half_vertical")
        + "</div>"))
    (out / "mashup_quadrants.html").write_text(PAGE.format(
        body=shared + '<div class="mashup mashup--2x2">'
        + "".join(r("quadrant").replace('ukgrid-q"', f'ukgrid-q{i}"').replace("ukgrid-chart-q", f"ukgrid-chart-q{i}") for i in range(4))
        + "</div>"))
    print(f"wrote previews to {out} ({settings})")


if __name__ == "__main__":
    main()
