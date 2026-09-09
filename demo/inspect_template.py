"""Ingest-extract preview: read a real .dotx template's style inventory.

This is a *preview* of the ingest step (ADR-0009), not the finished thing. It
does two of the jobs ingest will do:

  1. Open a .dotx. A template's OOXML content type is the template main-part
     type, which document readers reject, so we read the package directly.
  2. Extract the style inventory keyed by w:styleId, with the display name and
     whether the style is custom, because the display name alone is not a stable
     key (see docs/ingest-notes.md).

It renders nothing: retaining a real title page needs the zone model, which is
not built yet. Point it at a template, or let it scan demo templates:

    python demo/inspect_template.py path/to/template.dotx

If no path is given it looks in "tests/example documents" and skips cleanly when
that folder is absent (its contents are confidential and gitignored).
"""

from __future__ import annotations

import collections
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = Path(__file__).resolve().parent.parent


def inventar(pfad: Path) -> None:
    z = zipfile.ZipFile(pfad)
    namen = set(z.namelist())
    ist_vorlage = b"template.main+xml" in z.read("[Content_Types].xml")

    stile: list[tuple[str, str, str, bool]] = []  # (styleId, name, type, custom)
    if "word/styles.xml" in namen:
        root = ET.fromstring(z.read("word/styles.xml"))
        for s in root.findall(f"{W}style"):
            sid = s.get(f"{W}styleId") or ""
            nm_el = s.find(f"{W}name")
            nm = nm_el.get(f"{W}val") if nm_el is not None else sid
            stile.append((sid, nm, s.get(f"{W}type") or "", s.get(f"{W}customStyle") == "1"))

    genutzt: collections.Counter[str] = collections.Counter()
    sektionen = 0
    if "word/document.xml" in namen:
        d = ET.fromstring(z.read("word/document.xml"))
        for ps in d.iter(f"{W}pStyle"):
            genutzt[ps.get(f"{W}val") or ""] += 1
        sektionen = len(list(d.iter(f"{W}sectPr")))

    kopf = sum(1 for n in namen if n.startswith("word/header"))
    custom = [s for s in stile if s[3]]

    print("=" * 68)
    print(pfad.name)
    print(f"  is .dotx template content type: {ist_vorlage}  (a document reader would reject it)")
    print(f"  sections: {sektionen}   headers: {kopf} (2 => different first page)")
    print(f"  styles: {len(stile)} total, {len(custom)} custom")
    print("  custom styles (styleId  <-  display name):")
    for sid, nm, typ, _ in custom:
        marke = "" if sid == nm.replace(" ", "") else "   <-- id != name"
        print(f"      {sid:34} {nm!r} [{typ}]{marke}")
    print("  most-used styles in the body (by styleId):")
    for sid, n in genutzt.most_common(10):
        print(f"      {sid:34} x{n}")


def main() -> None:
    if len(sys.argv) > 1:
        ziele = [Path(sys.argv[1])]
    else:
        ordner = ROOT / "tests" / "example documents"
        if not ordner.is_dir():
            print(
                "No template given and 'tests/example documents' is absent, "
                "so there is nothing to inspect. Pass a .dotx path to try it."
            )
            return
        ziele = sorted(ordner.glob("*.dotx"))
        if not ziele:
            print(f"No .dotx found in {ordner}.")
            return
    for z in ziele:
        inventar(z)


if __name__ == "__main__":
    main()
