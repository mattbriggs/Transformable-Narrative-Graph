"""Narrative tension scoring for GraphML edge visualisation.

Tension is a composite score in [0.0, 1.0] derived from three sources:

1. **Relationship type** — causal/preventive relations carry more tension than
   temporal ones (base scores defined in ``RELATION_BASE``).
2. **Barthesian codes** — atoms tagged with HERMENEUTIC or PROAIRETIC codes
   signal unresolved mystery or imminent action, boosting tension.
3. **Scene mood** — high arousal combined with negative valence produces the
   anxious state associated with peak narrative tension.

The final score is clamped to [0.0, 1.0] and mapped through a six-stop
perceptual gradient from neutral grey to deep red.  The colour values are
chosen so that even viewers with common forms of colour-vision deficiency can
perceive the low→high gradient (grey→blue is distinguishable from grey→red
for protanopia/deuteranopia).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from tng.domain.enums import BarthesCode
from tng.domain.models import Atom, MoodState

# ── Base tension by relationship type ────────────────────────────────────────

RELATION_BASE: dict[str, float] = {
    "PREVENTS": 0.9,
    "CAUSES": 0.7,
    "PARTICIPATES_IN": 0.4,
    "ENABLES": 0.4,
    "PRECEDES": 0.2,
}

_STRUCTURAL_BASE = 0.0  # HAS_SCENE, CONTAINS, INSTANCE_OF, etc.

# ── Barthesian code modifiers (additive) ─────────────────────────────────────

_CODE_MODIFIER: dict[BarthesCode, float] = {
    BarthesCode.HERMENEUTIC: 0.4,
    BarthesCode.PROAIRETIC: 0.3,
    BarthesCode.SYMBOLIC: 0.2,
    BarthesCode.SEMIC: 0.1,
    BarthesCode.CULTURAL: 0.0,
}

# ── Six-stop perceptual colour gradient (hex RGB) ────────────────────────────
# 0.0 → grey, 0.2 → steel-blue, 0.4 → gold, 0.6 → orange,
# 0.8 → crimson-red, 1.0 → dark blood-red

_GRADIENT: list[tuple[float, tuple[int, int, int]]] = [
    (0.0, (160, 160, 160)),  # grey
    (0.2, (70, 130, 180)),   # steel-blue
    (0.4, (218, 165, 32)),   # golden-rod
    (0.6, (255, 140, 0)),    # dark-orange
    (0.8, (220, 20, 60)),    # crimson
    (1.0, (139, 0, 0)),      # dark-red
]


# ── Public API ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TensionScore:
    """Tension assessment for a single edge.

    :param score: Composite tension value in [0.0, 1.0].
    :param hex_color: Six-character hex RGB string (e.g. ``"#DC143C"``).
    :param base: Base score from relationship type alone.
    :param code_bonus: Additive modifier from Barthesian codes.
    :param mood_bonus: Additive modifier from scene mood.
    """

    score: float
    hex_color: str
    base: float
    code_bonus: float
    mood_bonus: float


def score_edge(
    relation_type: str,
    atoms: Sequence[Atom] | None = None,
    mood: MoodState | None = None,
) -> TensionScore:
    """Compute a tension score for a single graph edge.

    :param relation_type: The Cypher relationship type string
        (e.g. ``"CAUSES"``, ``"HAS_SCENE"``).
    :param atoms: Atoms in the source scene whose code tags contribute
        Barthesian code modifiers.  Pass ``None`` or empty to skip.
    :param mood: The active ``MoodState`` of the source scene.  Pass ``None``
        to skip the mood contribution.
    :returns: A ``TensionScore`` with the final score and rendered colour.
    """
    base = RELATION_BASE.get(relation_type, _STRUCTURAL_BASE)

    code_bonus = _code_bonus(atoms or [])
    mood_bonus = _mood_bonus(mood)

    raw = base + code_bonus + mood_bonus
    clamped = max(0.0, min(1.0, raw))

    return TensionScore(
        score=round(clamped, 4),
        hex_color=_interpolate_color(clamped),
        base=base,
        code_bonus=round(code_bonus, 4),
        mood_bonus=round(mood_bonus, 4),
    )


def score_structural_edge(label: str = "") -> TensionScore:
    """Return a zero-tension score for structural/containment edges.

    :param label: Optional label for the edge (unused, kept for call-site
        readability).
    :returns: A ``TensionScore`` at 0.0 mapped to grey.
    """
    return score_edge(label or "_structural")


# ── Internal helpers ──────────────────────────────────────────────────────────


def _code_bonus(atoms: Sequence[Atom]) -> float:
    """Sum the highest Barthesian code modifier across all atom tags.

    Only the single highest-ranking code per call site contributes so that
    heavily tagged scenes do not produce unrealistic tension inflation.

    :param atoms: Atoms whose ``code_tags`` are inspected.
    :returns: Additive modifier in [0.0, 0.4].
    """
    best = 0.0
    for atom in atoms:
        for tag in atom.code_tags:
            modifier = _CODE_MODIFIER.get(tag.code, 0.0)
            if modifier > best:
                best = modifier
    return best


def _mood_bonus(mood: MoodState | None) -> float:
    """Derive a mood-based tension modifier.

    High arousal combined with negative valence is the anxious/threatening
    mood profile most associated with narrative tension.  The formula maps
    the (valence, arousal) plane to [0.0, 0.3]:

        mood_bonus = arousal * max(0, -valence) * 0.6

    :param mood: The active ``MoodState``, or ``None``.
    :returns: Additive modifier in [0.0, 0.3].
    """
    if mood is None:
        return 0.0
    negative_valence = max(0.0, -mood.valence)  # valence in [-1, 1]
    return mood.arousal * negative_valence * 0.6


def _interpolate_color(t: float) -> str:
    """Map *t* ∈ [0.0, 1.0] to a hex colour via the six-stop gradient.

    Performs linear interpolation between the two nearest gradient stops.

    :param t: Normalised tension value.
    :returns: Hex colour string prefixed with ``#``.
    """
    if t <= _GRADIENT[0][0]:
        r, g, b = _GRADIENT[0][1]
        return f"#{r:02X}{g:02X}{b:02X}"
    if t >= _GRADIENT[-1][0]:
        r, g, b = _GRADIENT[-1][1]
        return f"#{r:02X}{g:02X}{b:02X}"

    for i in range(len(_GRADIENT) - 1):
        lo_t, lo_rgb = _GRADIENT[i]
        hi_t, hi_rgb = _GRADIENT[i + 1]
        if lo_t <= t <= hi_t:
            ratio = (t - lo_t) / (hi_t - lo_t)
            r = int(lo_rgb[0] + ratio * (hi_rgb[0] - lo_rgb[0]))
            g = int(lo_rgb[1] + ratio * (hi_rgb[1] - lo_rgb[1]))
            b = int(lo_rgb[2] + ratio * (hi_rgb[2] - lo_rgb[2]))
            return f"#{r:02X}{g:02X}{b:02X}"

    r, g, b = _GRADIENT[-1][1]
    return f"#{r:02X}{g:02X}{b:02X}"
