"""MathML (as exported from Word into the FIPI bank) to inline LaTeX math."""

import re

from bs4.element import NavigableString, Tag

SYMBOLS = {
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ε": r"\varepsilon",
    "η": r"\eta",
    "θ": r"\theta",
    "λ": r"\lambda",
    "μ": r"\mu",
    "ν": r"\nu",
    "π": r"\pi",
    "ρ": r"\rho",
    "σ": r"\sigma",
    "τ": r"\tau",
    "υ": r"\upsilon",
    "φ": r"\varphi",
    "ω": r"\omega",
    "Δ": r"\Delta",
    "Φ": r"\Phi",
    "Ω": r"\Omega",
    "·": r"\cdot",
    "⋅": r"\cdot",
    "×": r"\times",
    "−": "-",
    "–": "-",
    "≈": r"\approx",
    "≤": r"\le",
    "≥": r"\ge",
    "≠": r"\ne",
    "→": r"\to",
    "∞": r"\infty",
    "°": r"^\circ",
    "±": r"\pm",
    "√": r"\sqrt{}",
    "∆": r"\Delta",
}
ACCENTS = {"→": r"\vec", "¯": r"\overline", "‾": r"\overline", "^": r"\hat", "˙": r"\dot"}
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
COMMAND = re.compile(r"^\\[A-Za-z]+$")
NUMBER = re.compile(r"^[\d,.]+$")


def local_name(tag: Tag) -> str:
    return tag.name.rsplit(":", 1)[-1].lower()


def symbols(text: str) -> str:
    out = []
    for char in text:
        command = SYMBOLS.get(char, char)
        out.append(command + " " if command[0] == "\\" and command[-1].isalpha() else command)
    return "".join(out).strip()


def leaf(text: str) -> str:
    text = " ".join(text.split())
    if CYRILLIC.search(text):
        return r"\text{" + text + "}"
    return symbols(text)


def group(text: str) -> str:
    return text if len(text) == 1 or COMMAND.match(text) else "{" + text + "}"


def children(tag: Tag) -> list[Tag]:
    return [child for child in tag.children if isinstance(child, Tag)]


def convert(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return leaf(str(node))
    name = local_name(node)
    args = children(node)
    if name in {"mi", "mn", "mo", "ms"}:
        return leaf(node.get_text())
    if name == "mtext":
        text = " ".join(node.get_text().split())
        if not text:
            return "~"
        return r"\text{" + text + "}" if CYRILLIC.search(text) or " " in text else symbols(text)
    if name == "mspace":
        return "~"
    if name in {"annotation", "annotation-xml", "mphantom", "none", "mprescripts"}:
        return ""
    if name == "semantics":
        return convert(args[0]) if args else ""
    if name == "mfrac" and len(args) == 2:
        return r"\frac{" + convert(args[0]) + "}{" + convert(args[1]) + "}"
    if name == "msqrt":
        return r"\sqrt{" + row(args) + "}"
    if name == "mroot" and len(args) == 2:
        return r"\sqrt[" + convert(args[1]) + "]{" + convert(args[0]) + "}"
    if name in {"msub", "munder"} and len(args) == 2:
        return group(convert(args[0])) + "_" + group(convert(args[1]))
    if name in {"msup"} and len(args) == 2:
        return group(convert(args[0])) + "^" + group(convert(args[1]))
    if name in {"msubsup", "munderover"} and len(args) == 3:
        base, low, high = (convert(arg) for arg in args)
        return group(base) + "_" + group(low) + "^" + group(high)
    if name == "mmultiscripts" and args:
        return multiscripts(args)
    if name == "mover" and len(args) == 2:
        accent = ACCENTS.get(args[1].get_text().strip())
        if accent:
            return accent + "{" + convert(args[0]) + "}"
        return r"\overset{" + convert(args[1]) + "}{" + convert(args[0]) + "}"
    if name == "mfenced":
        opening = str(node.get("open", "("))
        closing = str(node.get("close", ")"))
        return r"\left" + opening + ", ".join(convert(a) for a in args) + r"\right" + closing
    if name == "mtable":
        return r"\begin{matrix}" + r" \\ ".join(convert(a) for a in args) + r"\end{matrix}"
    if name == "mtr":
        return " & ".join(convert(a) for a in args)
    return row(args)


def scripts(nodes: list[Tag]) -> str:
    low = " ".join(convert(node) for node in nodes[0::2]).strip()
    high = " ".join(convert(node) for node in nodes[1::2]).strip()
    return ("_{" + low + "}" if low else "") + ("^{" + high + "}" if high else "")


def multiscripts(args: list[Tag]) -> str:
    """Isotope notation and other pre-scripts: base, post pairs, <mprescripts/>, pre pairs."""

    names = [local_name(arg) for arg in args]
    split = names.index("mprescripts") if "mprescripts" in names else len(args)
    pre = scripts(args[split + 1 :])
    return ("{}" + pre if pre else "") + group(convert(args[0])) + scripts(args[1:split])


def row(nodes: list[Tag]) -> str:
    joined = ""
    previous = ""
    for part in (convert(node) for node in nodes):
        if not part:
            continue
        # Word splits one number into several <mn> elements: 1, 0 -> 10.
        glue = "" if NUMBER.match(previous) and NUMBER.match(part) else " "
        joined = joined + glue + part if joined else part
        previous = part
    return joined


def to_latex(math: Tag) -> str:
    """Inline LaTeX for one <m:math> element, without surrounding dollar signs."""

    latex = re.sub(r"\s+", " ", convert(math))
    # Spaces around operators and braces carry no meaning in math mode.
    return re.sub(r"\s*([=+\-,()^_{}~])\s*", r"\1", latex).strip()
