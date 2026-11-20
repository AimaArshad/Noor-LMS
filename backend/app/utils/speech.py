"""``speech_normalize`` — convert science/math text to natural spoken English.

Design
------
* Pure functions — no external dependencies, no I/O.
* Table-driven: ``UNIT_TABLE``, ``GREEK_TABLE``, ``ABBREV_TABLE``.
* All replacements are applied left-to-right on a single pass through the
  compiled regex list; ordering matters (more specific patterns first).
* Superscripts / subscripts handled via dedicated Unicode maps.
* "Fig. 2.1" → "Figure 2 point 1" — figure references spoken naturally.

Usage::

    from app.utils.speech import speech_normalize

    text = "v = 5 m/s at 20 °C, x² + H₂O"
    print(speech_normalize(text))
    # → "v equals 5 metres per second at 20 degrees Celsius, x squared plus H 2 O"
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Unicode superscript / subscript character maps
# ---------------------------------------------------------------------------

_SUPERSCRIPT_MAP: dict[str, str] = {
    "\u00b2": "squared",
    "\u00b3": "cubed",
    "\u2070": "to the power 0",
    "\u00b9": "to the power 1",
    "\u2074": "to the power 4",
    "\u2075": "to the power 5",
    "\u2076": "to the power 6",
    "\u2077": "to the power 7",
    "\u2078": "to the power 8",
    "\u2079": "to the power 9",
}

_SUBSCRIPT_MAP: dict[str, str] = {
    "\u2080": "0",
    "\u2081": "1",
    "\u2082": "2",
    "\u2083": "3",
    "\u2084": "4",
    "\u2085": "5",
    "\u2086": "6",
    "\u2087": "7",
    "\u2088": "8",
    "\u2089": "9",
}

# ---------------------------------------------------------------------------
# Greek letter map (lower + upper)
# ---------------------------------------------------------------------------

_GREEK_TABLE: dict[str, str] = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta",
    "ε": "epsilon", "ζ": "zeta", "η": "eta", "θ": "theta",
    "ι": "iota", "κ": "kappa", "λ": "lambda", "μ": "mu",
    "ν": "nu", "ξ": "xi", "ο": "omicron", "π": "pi",
    "ρ": "rho", "σ": "sigma", "τ": "tau", "υ": "upsilon",
    "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
    "Α": "Alpha", "Β": "Beta", "Γ": "Gamma", "Δ": "Delta",
    "Ε": "Epsilon", "Ζ": "Zeta", "Η": "Eta", "Θ": "Theta",
    "Ι": "Iota", "Κ": "Kappa", "Λ": "Lambda", "Μ": "Mu",
    "Ν": "Nu", "Ξ": "Xi", "Ο": "Omicron", "Π": "Pi",
    "Ρ": "Rho", "Σ": "Sigma", "Τ": "Tau", "Υ": "Upsilon",
    "Φ": "Phi", "Χ": "Chi", "Ψ": "Psi", "Ω": "Omega",
}

# ---------------------------------------------------------------------------
# Abbreviation table: common Latin abbreviations + figure references
# ---------------------------------------------------------------------------

_ABBREV_TABLE: list[tuple[str, str]] = [
    # Figure references: "Fig. 2.1" → "Figure 2 point 1"
    # Must handle multi-part numbers like "Fig. 2.1.3"
    # Handled by a regex further below.

    ("e.g.", "for example"),
    ("i.e.", "that is"),
    ("et al.", "and others"),
    ("etc.", "et cetera"),
    ("vs.", "versus"),
    ("approx.", "approximately"),
    ("dept.", "department"),
    ("no.", "number"),
    ("vol.", "volume"),
]

# ---------------------------------------------------------------------------
# Unit table: (regex_pattern, replacement_template)
# Ordered most-specific → least-specific to avoid partial matches.
# ---------------------------------------------------------------------------

# Combined units (must come before single units)
_UNIT_PATTERNS: list[tuple[str, str]] = [
    # Speed: m/s, km/h, mph, ft/s
    (r"\bm/s\b",      "metres per second"),
    (r"\bkm/h\b",     "kilometres per hour"),
    (r"\bmph\b",      "miles per hour"),
    (r"\bft/s\b",     "feet per second"),
    # Acceleration
    (r"\bm/s²\b",     "metres per second squared"),
    (r"\bm/s\^2\b",   "metres per second squared"),
    # Force / Pressure / Energy / Power
    (r"\bN·m\b",      "newton metres"),
    (r"\bN·m/s\b",    "newton metres per second"),
    (r"\bJ/mol\b",    "joules per mole"),
    (r"\bJ/kg\b",     "joules per kilogram"),
    (r"\bW/m²\b",     "watts per square metre"),
    (r"\bW/m\^2\b",   "watts per square metre"),
    # Temperature
    (r"°C\b",         "degrees Celsius"),
    (r"°F\b",         "degrees Fahrenheit"),
    (r"°K\b",         "kelvin"),          # unusual but keep
    (r"\bK\b(?=\s|$|\))", "kelvin"),     # SI: 300 K
    # Length
    (r"\bkm\b",       "kilometres"),
    (r"\bcm\b",       "centimetres"),
    (r"\bmm\b",       "millimetres"),
    (r"\bnm\b",       "nanometres"),
    (r"\bμm\b",       "micrometres"),
    (r"\bpm\b",       "picometres"),
    (r"\bm\b(?=\s|\d|$|\))", "metres"),
    (r"\bft\b",       "feet"),
    (r"\bin\b(?=\s|\d|$|\))", "inches"),
    # Mass
    (r"\bkg\b",       "kilograms"),
    (r"\bmg\b",       "milligrams"),
    (r"\bμg\b",       "micrograms"),
    (r"\bg\b(?=\s|\d|$|\))", "grams"),
    # Time
    (r"\bms\b",       "milliseconds"),
    (r"\bμs\b",       "microseconds"),
    (r"\bns\b",       "nanoseconds"),
    (r"\bhr\b",       "hours"),
    (r"\bmin\b",      "minutes"),
    (r"\bs\b(?=\s|\d|$|\))", "seconds"),
    # Energy / Power
    (r"\bkJ\b",       "kilojoules"),
    (r"\bMJ\b",       "megajoules"),
    (r"\bJ\b(?=\s|\d|$|\))", "joules"),
    (r"\bkW\b",       "kilowatts"),
    (r"\bMW\b",       "megawatts"),
    (r"\bW\b(?=\s|\d|$|\))", "watts"),
    # Force / Pressure
    (r"\bkN\b",       "kilonewtons"),
    (r"\bN\b(?=\s|\d|$|\))", "newtons"),
    (r"\bkPa\b",      "kilopascals"),
    (r"\bMPa\b",      "megapascals"),
    (r"\bPa\b(?=\s|\d|$|\))", "pascals"),
    (r"\bbar\b",      "bar"),
    (r"\batm\b",      "atmospheres"),
    # Electricity
    (r"\bkV\b",       "kilovolts"),
    (r"\bV\b(?=\s|\d|$|\))", "volts"),
    (r"\bmA\b",       "milliamps"),
    (r"\bμA\b",       "microamps"),
    (r"\bA\b(?=\s|\d|$|\))", "amps"),
    (r"\bΩ\b",        "ohms"),
    (r"\bkΩ\b",       "kilohms"),
    (r"\bMΩ\b",       "megohms"),
    (r"\bμF\b",       "microfarads"),
    (r"\bmF\b",       "millifarads"),
    (r"\bF\b(?=\s|\d|$|\))", "farads"),
    (r"\bH\b(?=\s|\d|$|\))", "henries"),
    (r"\bmH\b",       "millihenries"),
    # Frequency
    (r"\bGHz\b",      "gigahertz"),
    (r"\bMHz\b",      "megahertz"),
    (r"\bkHz\b",      "kilohertz"),
    (r"\bHz\b",       "hertz"),
    # Volume
    (r"\bmL\b",       "millilitres"),
    (r"\bμL\b",       "microlitres"),
    (r"\bL\b(?=\s|\d|$|\))", "litres"),
    # Moles
    (r"\bmol\b",      "moles"),
    (r"\bmmol\b",     "millimoles"),
    (r"\bμmol\b",     "micromoles"),
    # Angle
    (r"°\b",          "degrees"),
    (r"\brad\b",      "radians"),
]

# ---------------------------------------------------------------------------
# Operator symbols
# ---------------------------------------------------------------------------

_OPERATOR_PATTERNS: list[tuple[str, str]] = [
    (r"\s*×\s*",   " times "),
    (r"\s*÷\s*",   " divided by "),
    (r"\s*±\s*",   " plus or minus "),
    (r"\s*≠\s*",   " not equal to "),
    (r"\s*≤\s*",   " less than or equal to "),
    (r"\s*≥\s*",   " greater than or equal to "),
    (r"\s*→\s*",   " gives "),
    (r"\s*⇌\s*",   " in equilibrium with "),
    (r"\s*∝\s*",   " is proportional to "),
    (r"\s*∞\b",    " infinity"),
    (r"\s*√\s*",   " the square root of "),
]

# ---------------------------------------------------------------------------
# Percentage
# ---------------------------------------------------------------------------

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# ---------------------------------------------------------------------------
# Figure / Table references: "Fig. 2.1" or "Fig 2.1" or "Figure 2.1"
# ---------------------------------------------------------------------------

_FIG_RE = re.compile(
    r"\b(Fig(?:ure)?\.?|Table)\s+(\d+)(?:\.(\d+))*",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Compile all regex patterns once at module load
# ---------------------------------------------------------------------------

_UNIT_RE: list[tuple[re.Pattern, str]] = [
    (re.compile(pat), repl) for pat, repl in _UNIT_PATTERNS
]
_OPERATOR_RE: list[tuple[re.Pattern, str]] = [
    (re.compile(pat), repl) for pat, repl in _OPERATOR_PATTERNS
]


# ---------------------------------------------------------------------------
# Helper: expand superscripts/subscripts character by character
# ---------------------------------------------------------------------------

def _expand_unicode_scripts(text: str) -> str:
    """Replace Unicode superscript/subscript digits and common exponent chars."""
    out: list[str] = []
    for ch in text:
        if ch in _SUPERSCRIPT_MAP:
            out.extend([" ", _SUPERSCRIPT_MAP[ch], " "])
        elif ch in _SUBSCRIPT_MAP:
            out.extend([" ", _SUBSCRIPT_MAP[ch], " "])
        else:
            out.append(ch)
    return "".join(out)


def _expand_greek(text: str) -> str:
    """Replace Greek letters with English names."""
    for letter, name in _GREEK_TABLE.items():
        text = text.replace(letter, f" {name} ")
    return text


def _expand_abbrevs(text: str) -> str:
    for abbrev, expanded in _ABBREV_TABLE:
        # Case-insensitive whole-word match
        text = re.sub(re.escape(abbrev), expanded, text, flags=re.IGNORECASE)
    return text


def _expand_fig_refs(text: str) -> str:
    """'Fig. 2.1' → 'Figure 2 point 1', 'Table 3.2' → 'Table 3 point 2'."""

    def _repl(m: re.Match) -> str:
        keyword = m.group(1)
        label = "Figure" if keyword.lower().startswith("fig") else "Table"
        # Reconstruct the number parts from the full match text
        num_part = m.group(0).split()[-1]  # e.g. "2.1" or "3.2.1"
        parts = num_part.split(".")
        spoken = " point ".join(parts)
        return f"{label} {spoken}"

    return _FIG_RE.sub(_repl, text)


def _expand_percentages(text: str) -> str:
    return _PERCENT_RE.sub(lambda m: f"{m.group(1)} percent", text)


def _expand_operators(text: str) -> str:
    for pat, repl in _OPERATOR_RE:
        text = pat.sub(repl, text)
    return text


def _expand_units(text: str) -> str:
    for pat, repl in _UNIT_RE:
        text = pat.sub(repl, text)
    return text


def _collapse_spaces(text: str) -> str:
    """Collapse multiple spaces (but preserve line breaks)."""
    lines = text.split("\n")
    return "\n".join(" ".join(line.split()) for line in lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def speech_normalize(text: str) -> str:
    """Convert science/math text to naturally speakable English.

    Applies transformations in this order:
    1. Unicode superscript/subscript character expansion
    2. Greek letter expansion
    3. Figure/table reference expansion
    4. Abbreviation expansion (e.g., i.e., Fig.)
    5. Percentage expansion
    6. Operator symbol expansion (×, ÷, ±, …)
    7. Unit expansion (m/s, °C, kg, …)
    8. Whitespace collapse

    Args:
        text: Raw text from a document page or segment.

    Returns:
        A string suitable for text-to-speech synthesis.
    """



    if not text:
        return text

    # Ohm sign must be handled before the Greek-letter step turns it into "Omega"
    text = re.sub(r"(?<=\d)\s*[\u03A9\u2126]", " ohms", text)

    text = _expand_unicode_scripts(text)
    text = _expand_greek(text)
    text = _expand_fig_refs(text)
    text = _expand_abbrevs(text)
    text = _expand_percentages(text)
    text = _expand_operators(text)
    text = _expand_units(text)
    text = _collapse_spaces(text)
    return text

