"""Thin wrapper around the pandoc CLI.

Pandoc is used only as the Markdown parser and serialiser for the editing
surface (ADR-0012). It is never the canonical data model and never the renderer.

The mapping layer is version-agnostic: we detect this pandoc's
``pandoc-api-version`` at runtime and echo it back when we hand JSON to pandoc,
rather than hardcoding one. That is ADR-0012's "pin the version, own the
mapping" made concrete, and it is why an old pandoc (2.9) and a new one (3.x)
can both drive this code.

Extension tuning matters for a faithful round trip and is deliberate:

* ``-smart``            keeps ``"`` and ``--`` literal instead of turning them
                        into typographic quotes and dashes on read.
* ``-auto_identifiers`` stops pandoc inventing ``{#slug}`` ids for headings.
* ``--wrap=none``       stops the writer inserting line breaks, which would turn
                        ``Space`` into ``SoftBreak``.
"""

from __future__ import annotations

import functools
import json
import subprocess
from typing import Any

# Read and write with the same extension set so the round trip is symmetric.
_FORMAT = "markdown-smart-auto_identifiers"


def _run(args: list[str], stdin: str) -> str:
    proc = subprocess.run(
        ["pandoc", *args],
        input=stdin.encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "pandoc failed (" + " ".join(args) + "): " + proc.stderr.decode("utf-8", "replace")
        )
    return proc.stdout.decode("utf-8")


@functools.lru_cache(maxsize=1)
def api_version() -> list[int]:
    """The pandoc-api-version of the installed pandoc, e.g. ``[1, 20]``."""
    doc = json.loads(_run(["-f", _FORMAT, "-t", "json"], ""))
    ver = doc["pandoc-api-version"]
    return [int(x) for x in ver]


def markdown_to_blocks(md: str) -> list[dict[str, Any]]:
    """Parse Markdown body text into pandoc block dicts."""
    doc = json.loads(_run(["-f", _FORMAT, "-t", "json"], md))
    return list(doc["blocks"])


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Serialise pandoc block dicts to Markdown body text."""
    envelope = {
        "pandoc-api-version": api_version(),
        "meta": {},
        "blocks": blocks,
    }
    out = _run(["-f", "json", "-t", _FORMAT, "--wrap=none"], json.dumps(envelope))
    return out
