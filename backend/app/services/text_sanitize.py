"""Convert LLM-emitted LaTeX/markdown artifacts into plain readable text.

Generated lesson content and tutor answers sometimes contain raw LaTeX
($82^{\\circ}30' E$) or markdown emphasis that the UI renders verbatim.
This module turns those fragments into plain unicode prose so kids never
see dollar signs or asterisks. It only rewrites presentation, never facts.
"""

import re

_LATEX_TEXT = re.compile(r"\\text\{([^{}]*)\}")
_LATEX_FRAC = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_LATEX_SQRT = re.compile(r"\\sqrt\{([^{}]*)\}")
_LATEX_SUP = re.compile(r"\^\{([^{}]*)\}")
_LATEX_SUB = re.compile(r"_\{([^{}]*)\}")
_LATEX_CMD_WORD = re.compile(r"\\[a-zA-Z]+\b")

_LATEX_COMMANDS = {
    r"\times": "×",
    r"\div": "÷",
    r"\pm": "±",
    r"\approx": "≈",
    r"\degree": "°",
    r"\pi": "π",
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\theta": "θ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\Omega": "Ω",
    r"\Delta": "Δ",
    r"\Rightarrow": "→",
    r"\rightarrow": "→",
    r"\leftarrow": "←",
    r"\le": "≤",
    r"\leq": "≤",
    r"\ge": "≥",
    r"\geq": "≥",
    r"\neq": "≠",
    r"\cdot": "·",
    r"\ldots": "…",
}

_MD_ASTERISKS = re.compile(r"\*{1,3}([^*\n]+?)\*{1,3}")
_MD_BACKTICKS = re.compile(r"`([^`\n]+)`")
_MD_UNDERSCORES = re.compile(r"_{2,}([^_\n]+?)_{2,}")
_MD_HEADING = re.compile(r"(?m)^#{1,6}\s+")

_SUPERSCRIPT = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "circ": "°", "o": "°", "∘": "°",
}
_SUBSCRIPT = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
}


def _superscript_text(value: str) -> str:
    value = value.strip()
    if value in _SUPERSCRIPT:
        return _SUPERSCRIPT[value]
    if value == r"\circ":
        return "°"
    return f"^{value}"


def _subscript_text(value: str) -> str:
    value = value.strip()
    if value in _SUBSCRIPT:
        return _SUBSCRIPT[value]
    return f"_{value}"


def sanitize_prose(text: str) -> str:
    """Rewrite presentation artifacts in a generated string; keep the facts."""
    if not text:
        return ""
    out = str(text).replace("\r\n", "\n").replace("\r", "\n")

    out = _LATEX_TEXT.sub(r"\1", out)
    out = _LATEX_FRAC.sub(lambda m: f"({m.group(1)}/{m.group(2)})", out)
    out = _LATEX_SQRT.sub(lambda m: f"√({m.group(1)})", out)
    out = _LATEX_SUP.sub(lambda m: _superscript_text(m.group(1)), out)
    out = _LATEX_SUB.sub(lambda m: _subscript_text(m.group(1)), out)
    for command, replacement in _LATEX_COMMANDS.items():
        out = out.replace(command, replacement)
    out = _LATEX_CMD_WORD.sub("", out)
    out = out.replace("$", "").replace("\\,", " ").replace("\\ ", " ")
    out = re.sub(r"[{}]", " ", out)

    out = _MD_ASTERISKS.sub(r"\1", out)
    out = _MD_BACKTICKS.sub(r"\1", out)
    out = _MD_UNDERSCORES.sub(r"\1", out)
    out = _MD_HEADING.sub("", out)
    out = out.replace("**", "").replace("__", "")

    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def sanitize_tree(value):
    """Recursively sanitize every string inside a JSON-ish tree."""
    if isinstance(value, str):
        return sanitize_prose(value)
    if isinstance(value, dict):
        return {key: sanitize_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tree(item) for item in value]
    return value
