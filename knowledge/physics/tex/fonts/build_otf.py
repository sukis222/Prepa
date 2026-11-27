import re
from pathlib import Path

from fontTools.agl import toUnicode
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.t1Lib import T1Font
from fontTools.tfmLib import TFM

base = Path(__file__).resolve().parents[2] / "yakovlev-1-16" / "fonts"
out = Path(__file__).resolve().parent
encoding_text = (base / "cm-super-t2a.enc").read_text()
encoding_text = "\n".join(line.split("%")[0] for line in encoding_text.splitlines())
encoding = re.findall(r"/([^\s\[\]]+)", encoding_text)[1:]
scale = 10
for path in base.glob("*.pfb"):
    src = T1Font(str(path))
    src.parse()
    glyphs = src.getGlyphSet()
    order = list(glyphs)
    order.remove(".notdef")
    order.insert(0, ".notdef")
    cmap = {}
    strings = {}
    metrics = {}
    for name in order:
        glyph = glyphs[name]
        pen = T2CharStringPen(None, glyphs)
        glyph.draw(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
        width = round(glyph.width * scale)
        pen._width = width
        strings[name] = pen.getCharString(private=None, globalSubrs=None)
        bounds = BoundsPen(glyphs)
        glyph.draw(bounds)
        lsb = round(bounds.bounds[0] * scale) if bounds.bounds else 0
        metrics[name] = (width, lsb)
        uni = toUnicode(name)
        if len(uni) == 1:
            cmap.setdefault(ord(uni), name)
    fb = FontBuilder(1000 * scale, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=942 * scale, descent=-320 * scale)
    family = "CM Super Replica " + path.stem
    fb.setupNameTable(
        {
            "familyName": family,
            "styleName": "Regular",
            "uniqueFontIdentifier": family,
            "fullName": family,
            "psName": "CMReplica-" + path.stem,
            "version": "Version 1.0",
        }
    )
    fb.setupOS2(
        sTypoAscender=750 * scale,
        sTypoDescender=-250 * scale,
        sTypoLineGap=0,
        usWinAscent=942 * scale,
        usWinDescent=320 * scale,
    )
    fb.setupPost(italicAngle=src.font["FontInfo"]["ItalicAngle"])
    fb.setupCFF(
        "CMReplica-" + path.stem,
        {"FullName": family, "FamilyName": family, "Weight": src.font["FontInfo"]["Weight"]},
        strings,
        {},
    )
    fb.setupMaxp()
    tfmname = (
        path.stem.replace("sfrm", "larm").replace("sfbx", "labx").replace("sfti", "lati") + ".tfm"
    )
    tfmpath = base / tfmname
    if tfmpath.exists():
        tfm = TFM(str(tfmpath))
        kern = []
        liga = []
        for left, rights in tfm.kerning.items():
            for right, value in rights.items():
                if left < len(encoding) and right < len(encoding):
                    a, b = encoding[left], encoding[right]
                    if a in glyphs and b in glyphs:
                        kern.append(f"pos \\{a} \\{b} {round(value * 1000 * scale)};")
        for left, rights in tfm.ligatures.items():
            for right, (op, repl) in rights.items():
                if op == "LIG" and max(left, right, repl) < len(encoding):
                    a, b, c = [encoding[v] for v in (left, right, repl)]
                    if all(v in glyphs for v in (a, b, c)):
                        liga.append(f"sub \\{a} \\{b} by \\{c};")
        features = "languagesystem DFLT dflt; languagesystem cyrl dflt; languagesystem latn dflt;\n"
        if kern:
            features += "feature kern {\n" + "\n".join(kern) + "\n} kern;\n"
        if liga:
            features += "feature liga {\n" + "\n".join(liga) + "\n} liga;\n"
        addOpenTypeFeaturesFromString(fb.font, features)
    fb.save(out / (path.stem + ".otf"))
    print(path.stem, len(order), len(cmap), metrics["A"])
