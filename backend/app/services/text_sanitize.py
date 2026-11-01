"""Convert LLM-emitted LaTeX/markdown artifacts into clean, readable text.

Generated lesson content and tutor answers sometimes contain raw LaTeX
($82^{\\circ}30' E$, \\( E = mc^2 \\)) or markdown emphasis that the UI renders verbatim.
This module turns those fragments into plain unicode prose and clean bullet points
so students never see dollar signs, backslashes, or asterisks.
It only rewrites presentation, never facts.
"""

import re

# LaTeX command wrappers with curly braces
_LATEX_FORMATTERS = re.compile(
    r"\\(?:text|textbf|textit|mathbf|mathrm|mathit|underline|operatorname|bm)\{([^{}]*)\}"
)
_LATEX_FRAC = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_LATEX_SQRT = re.compile(r"\\sqrt\{([^{}]*)\}")
_LATEX_SUP = re.compile(r"\^\{([^{}]*)\}")
_LATEX_SUB = re.compile(r"_\{([^{}]*)\}")

_LATEX_COMMANDS = {
    r"\times": "×",
    r"\div": "÷",
    r"\pm": "±",
    r"\approx": "≈",
    r"\degree": "°",
    r"^\circ": "°",
    r"\circ": "°",
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
    r"\to": "→",
    r"\leftarrow": "←",
    r"\le": "≤",
    r"\leq": "≤",
    r"\ge": "≥",
    r"\geq": "≥",
    r"\neq": "≠",
    r"\cdot": "·",
    r"\cdots": "…",
    r"\ldots": "…",
    r"\infty": "∞",
}

# Math delimiters like \( ... \), \[ ... \], $$ ... $$, $ ... $
_MATH_OPEN_CLOSE = re.compile(r"\\[\(\)\[\]]")
_LATEX_CMD_WORD = re.compile(r"\\[a-zA-Z]+\b")

_MD_ASTERISKS = re.compile(r"\*{1,3}([^*\n]+?)\*{1,3}")
_MD_BACKTICKS = re.compile(r"`([^`\n]+)`")
_MD_UNDERSCORES = re.compile(r"_{2,}([^_\n]+?)_{2,}")
_MD_HEADING = re.compile(r"(?m)^#{1,6}\s+")
_BULLET_LIST = re.compile(r"(?m)^[\*\-]\s+")

_SUPERSCRIPT = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "circ": "°", "o": "°", "∘": "°", "+": "⁺", "-": "⁻",
}
_SUBSCRIPT = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋",
}


def _superscript_text(value: str) -> str:
    value = value.strip()
    if value in _SUPERSCRIPT:
        return _SUPERSCRIPT[value]
    if value in (r"\circ", "circ", "o"):
        return "°"
    if all(ch in _SUPERSCRIPT for ch in value):
        return "".join(_SUPERSCRIPT[ch] for ch in value)
    return f"^{value}"


def _subscript_text(value: str) -> str:
    value = value.strip()
    if value in _SUBSCRIPT:
        return _SUBSCRIPT[value]
    if all(ch in _SUBSCRIPT for ch in value):
        return "".join(_SUBSCRIPT[ch] for ch in value)
    return f"_{value}"


def sanitize_prose(text: str) -> str:
    """Rewrite presentation artifacts in a generated string; keep the facts."""
    if not text:
        return ""
    out = str(text).replace("\r\n", "\n").replace("\r", "\n")

    # Map Private Use Area characters from decorative NCERT fonts back to ASCII
    out = "".join(
        chr(ord(ch) - 0xF000) if 0xF000 <= ord(ch) <= 0xF0FF
        else (" " if 0xE000 <= ord(ch) <= 0xF8FF or 0xFB00 <= ord(ch) <= 0xFFFD else ch)
        for ch in out
    )
    # Normalize fancy dashes and quotes to clean ASCII equivalents
    out = out.replace("—", " - ").replace("–", " - ").replace("―", " - ")
    out = out.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')

    # Remove unicode replacement char
    out = re.sub(r"\ufffd\?*", " ", out)

    # Standardize list bullets first before markdown emphasis processing
    # so line-initial asterisks (* bullet) do not collide with **bold** or *italic*
    out = _BULLET_LIST.sub("• ", out)

    # Clean math delimiters
    out = _MATH_OPEN_CLOSE.sub("", out)

    # Clean formatting commands and nested sub/superscripts before fractions
    for _ in range(3):
        out = _LATEX_FORMATTERS.sub(r"\1", out)
        out = _LATEX_SUP.sub(lambda m: _superscript_text(m.group(1)), out)
        out = _LATEX_SUB.sub(lambda m: _subscript_text(m.group(1)), out)
        out = _LATEX_SQRT.sub(lambda m: f"√({m.group(1)})", out)
        out = _LATEX_FRAC.sub(lambda m: f"({m.group(1)}/{m.group(2)})", out)

    # Command replacements
    for command, replacement in _LATEX_COMMANDS.items():
        out = out.replace(command, replacement)
    out = _LATEX_CMD_WORD.sub("", out)

    # Clean residual dollars and backslashes
    out = out.replace("$$", "").replace("$", "")
    out = out.replace(r"\,", " ").replace(r"\ ", " ").replace("\\", "")

    # Clean markdown
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
