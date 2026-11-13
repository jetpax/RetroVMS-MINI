#!/usr/bin/env python3
"""Copy a .kicad_pcb with the case models hidden, so a STEP export of the copy
holds only the board and its parts. The SMA bulkhead and its antenna are hidden
too: the printed case has no coax connector.

    python3 hide_case_models.py board.kicad_pcb out.kicad_pcb
"""
import sys

CASE_MODELS = ("Corrected.STEP", "Footed_part", "CKKB48", "rvms_mini_case",
               "sma.STEP", "SMA-panelmount", "antenna_WiFi")

src, dst = sys.argv[1:3]
lines = open(src).read().split("\n")
out, hidden = [], 0
for i, line in enumerate(lines):
    out.append(line)
    s = line.strip()
    if s.startswith('(model "') and any(m in s for m in CASE_MODELS):
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if nxt != "(hide yes)":
            indent = line[: len(line) - len(line.lstrip())]
            out.append(indent + "\t(hide yes)")
            hidden += 1
open(dst, "w").write("\n".join(out))
print("hid %d case model(s)" % hidden)
