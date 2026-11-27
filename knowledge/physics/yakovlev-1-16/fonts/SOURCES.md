# Font sources

LH metrics: https://ctan.math.illinois.edu/systems/texlive/tlnet/archive/lh.tar.xz
CM-Super Type 1 outlines and encoding/map: https://ctan.math.illinois.edu/systems/texlive/tlnet/archive/cm-super.tar.xz

Downloaded 2026-11-14. Original font notices remain embedded in PFB files.
CM-Super: Vladimir Volovich, GNU General Public License, with font embedding exception.
LH: Olga Lapko and coauthors; original package license must accompany redistribution.
Original package documentation is included as COPYING, README, and LH-README/LH-readme35*.1st.

`labx1440.tfm` was generated from the official CM-Super `sfbx1440.afm.gz` using TeX Live `afm2tfm -T cm-super-t2a.enc`. Its ligature/kern program was then rebuilt: all 1,247 encoded AFM kerning pairs are retained (nine distinct adjustments), and the standard T2A ligatures are copied from the original LH `labx1200.tfm`. The Cyrillic k-o pair is -0.030548 em. Character metrics remain those of the 14.4-point AFM; the separately calibrated QUAD=1.1 em and XHEIGHT=0.4443359375 em are preserved. Other TFM files are unchanged LH files.

`cyrillic-unicode.tex` is a project-authored Unicode-to-T2A adapter for XeTeX. It preserves readable UTF-8 TeX sources without loading fontspec.
