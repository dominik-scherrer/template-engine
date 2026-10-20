"""The format guide: what Markdown a given profile accepts.

Agents write Markdown; the profile decides what it may contain. The guide is
derived from the profile's role mapping, so it never promises a construct the
renderer would then refuse (a heading level with no style, a table).
"""

from __future__ import annotations

from template_engine import StyleProfile

__all__ = ["format_guide", "allowed_heading_levels", "sample_markdown"]


def allowed_heading_levels(profile: StyleProfile) -> list[int]:
    stufen = []
    for rolle in profile.rollen:
        if rolle.startswith("ueberschrift_"):
            try:
                stufen.append(int(rolle.removeprefix("ueberschrift_")))
            except ValueError:
                continue
    return sorted(stufen)


def format_guide(name: str, version: int, profile: StyleProfile) -> str:
    r = profile.rollen
    stufen = allowed_heading_levels(profile)
    erlaubt: list[str] = []
    if stufen:
        marken = ", ".join("#" * s + f" (level {s})" for s in stufen)
        erlaubt.append(f"- Headings: {marken}.")
    if "fliesstext" in r:
        erlaubt.append("- Paragraphs: plain text, separated by a blank line.")
    if "aufzaehlung" in r:
        erlaubt.append("- Bullet lists: `- item`, one line per item, no nesting.")
    if "nummerierte_liste" in r:
        erlaubt.append("- Numbered lists: `1. item`, one line per item, no nesting.")

    nicht = [
        "- No bold, italics, links, inline code or images: inline text is plain.",
        "- No tables, block quotes, code blocks, horizontal rules or HTML.",
        "- No nested lists, and no blank lines inside a list.",
    ]
    if stufen:
        verboten = [s for s in range(1, 7) if s not in stufen]
        if verboten:
            nicht.insert(0, "- No heading levels other than " + ", ".join(map(str, stufen)) + ".")
    else:
        nicht.insert(0, "- No headings: this profile maps none.")

    return "\n".join(
        [
            f"# Format guide for profile `{name}` (v{version})",
            "",
            "Write the document body as Markdown. The template supplies all styling "
            "(fonts, numbering, headers, footers, title page); do not try to format.",
            "",
            "## Allowed",
            *erlaubt,
            "",
            "## Not supported (rendering fails)",
            *nicht,
            "",
            "## Example",
            "```markdown",
            *_beispiel(profile, stufen),
            "```",
        ]
    )


def _beispiel(profile: StyleProfile, stufen: list[int]) -> list[str]:
    r = profile.rollen
    zeilen: list[str] = []
    if stufen:
        zeilen += ["#" * stufen[0] + " Initial situation", ""]
    if "fliesstext" in r:
        zeilen += ["The current system reaches the end of its support period in 2027.", ""]
    if len(stufen) > 1:
        zeilen += ["#" * stufen[1] + " Objectives", ""]
    if "aufzaehlung" in r:
        zeilen += ["- Replace the system before support ends", "- Keep migration effort low", ""]
    if "nummerierte_liste" in r:
        zeilen += ["1. Analyse requirements", "2. Run the procurement", ""]
    return zeilen[:-1] if zeilen and zeilen[-1] == "" else zeilen


def sample_markdown(profile: StyleProfile) -> str:
    """A longer sample using every mapped role once or more, for test renders."""
    r = profile.rollen
    stufen = allowed_heading_levels(profile)
    zeilen: list[str] = []

    def ueberschrift(stufe_index: int, text: str) -> None:
        if len(stufen) > stufe_index:
            zeilen.extend(["#" * stufen[stufe_index] + " " + text, ""])

    def absatz(text: str) -> None:
        if "fliesstext" in r:
            zeilen.extend([text, ""])

    ueberschrift(0, "Initial situation")
    absatz(
        "The current case management system reaches the end of its support period in 2027. "
        "It is used by around 400 staff in six departments and holds records going back to 2004."
    )
    ueberschrift(1, "Objectives")
    absatz("The replacement should meet the following objectives:")
    if "aufzaehlung" in r:
        zeilen += [
            "- Replace the system before support ends",
            "- Keep data migration effort low",
            "- Reduce licence and operating costs",
            "",
        ]
    ueberschrift(0, "Procedure")
    absatz("The project follows four steps:")
    if "nummerierte_liste" in r:
        zeilen += [
            "1. Analyse requirements with the departments",
            "2. Prepare and run the procurement",
            "3. Evaluate the offers and award the contract",
            "4. Plan the migration",
            "",
        ]
    ueberschrift(2, "Schedule")
    absatz("The procurement is to be published in the first quarter, with award in the third.")
    return "\n".join(zeilen).rstrip() + "\n"
