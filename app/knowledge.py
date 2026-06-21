from pathlib import Path

_KB = Path(__file__).parent.parent / "knowledge"

# Maps a normalised sport_type string to a filename under knowledge/sports/.
_SPORT_FILE: dict[str, str] = {
    "run": "road_running.md",
    "bike": "road_cycling.md",
    "swim": "swimming.md",
    "trail_run": "trail_running.md",
    "trail": "trail_running.md",
}

# Each entry: (required-sports frozenset, multisport filename).
# Checked in order; first match wins.  The athlete's sport set must be a
# *superset* of the required set for the combo file to apply.
_MULTISPORT_COMBOS: list[tuple[frozenset, str]] = [
    (frozenset({"triathlon"}), "triathlon.md"),
    (frozenset({"run", "bike", "swim"}), "triathlon.md"),
]


def load_knowledge(sport_types: list[str]) -> str:
    """Return concatenated knowledge-base markdown for the given sport types.

    Rules (applied in order):
    1. Always loads core_training_science.md.
    2. If sport_types matches a known multisport combo, appends the combo file
       and returns early — it supersedes individual sport files.
    3. Otherwise appends each matching sports/ file for the athlete's disciplines.
    4. If nothing matches a sport, returns core only (model falls back to
       general knowledge).
    """
    core_text = (_KB / "core_training_science.md").read_text(encoding="utf-8")
    sections = [core_text]

    sports = {s.lower().strip() for s in sport_types}

    for required, filename in _MULTISPORT_COMBOS:
        if required.issubset(sports):
            path = _KB / "multisport" / filename
            if path.exists():
                sections.append(path.read_text(encoding="utf-8"))
                return "\n\n---\n\n".join(sections)

    for sport in sport_types:
        filename = _SPORT_FILE.get(sport.lower().strip())
        if filename:
            path = _KB / "sports" / filename
            if path.exists():
                sections.append(path.read_text(encoding="utf-8"))

    return "\n\n---\n\n".join(sections)
