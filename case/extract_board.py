# Splits the board export into the shapes the case is built around, in the
# case frame, for build_case.py. Run by build.sh (FreeCAD, headless):
#
#   freecadcmd extract_board.py        (from this folder, after the STEP export)
#
# Case frame: z = 0 is the board's underside. x and y put the board's four M3
# holes where the real CKKB48 case has its standoffs, (+-26.7, -37.85) and
# (+-32.6, 24.85), so the case's centre is the real case's centre: its ears
# and cover screws keep the real positions. +y is the connector end.

import json
import os

import FreeCAD as App
import Part

V = App.Vector
HERE = os.getcwd()
B = os.path.join(HERE, "build")
STANDOFF_CENTROID_Y = -6.5   # mean y of the real case's four standoffs

sol = Part.read(os.path.join(B, "board.step")).Solids

# the board body: thin, its underside at z = 0, the largest in plan
def plan_area(s):
    b = s.BoundBox
    return b.XLength * b.YLength
bodies = [s for s in sol if abs(s.BoundBox.ZMin) < 0.01 and 1.0 < s.BoundBox.ZLength < 2.0]
board = max(bodies, key=plan_area)
others = [s for s in sol if not s.isSame(board)]
bb = board.BoundBox

# the board's M3 mounting holes (3.2 mm)
holes, seen = [], set()
for f in board.Faces:
    su = f.Surface
    if su.__class__.__name__ == "Cylinder" and abs(abs(su.Axis.z) - 1) < 1e-6 and 1.5 < su.Radius < 1.7:
        k = (round(su.Center.x, 3), round(su.Center.y, 3))
        if k not in seen:
            seen.add(k)
            holes.append(k)
assert len(holes) == 4, "expected the board's four M3 holes, found %d" % len(holes)
cx = sum(h[0] for h in holes) / 4
cy = sum(h[1] for h in holes) / 4
T = V(-cx, STANDOFF_CENTROID_Y - cy, 0)

def moved(s):
    c = s.copy()
    c.translate(T)
    return c

# connector: reaches past the board's far end and stands tall
conn = [s for s in others if s.BoundBox.YMax > bb.YMax + 5 and s.BoundBox.ZMax > 15]
comps = [s for s in others if not any(s.isSame(c) for c in conn)]
assert conn, "connector not found in the export"

for name, shapes in (("board", [board]), ("conn", conn), ("comps", comps)):
    Part.makeCompound([moved(s) for s in shapes]).exportBrep(os.path.join(B, "ref_%s.brep" % name))

# KiCad: the case STEP lines up on the connector footprint J1 with this offset
# (rotation 0). The STEP export's y is -y of the board file; models sit on the
# board's top face.
J1 = (65.3358, 63.3974)   # J1's position in the board file
# case x = x_board + T.x, case y = -y_board + T.y; a model point p lands at
# footprint offset (x_board - J1x, -(y_board - J1y), z - thickness)
frame = dict(
    translate=[T.x, T.y, T.z],
    board_thickness=bb.ZLength,
    board_holes=[[h[0] + T.x, h[1] + T.y] for h in holes],
    kicad_offset_on_J1=[-T.x - J1[0], -T.y + J1[1], -bb.ZLength],
)
json.dump(frame, open(os.path.join(B, "frame.json"), "w"), indent=1)
b2 = moved(board).BoundBox
print("board %.2f x %.2f, thickness %.2f; frame shift (%.3f, %.3f)" % (bb.XLength, bb.YLength, bb.ZLength, T.x, T.y))
print("board in case frame: x %.2f..%.2f  y %.2f..%.2f" % (b2.XMin, b2.XMax, b2.YMin, b2.YMax))
print("holes", [[round(v, 2) for v in h] for h in frame["board_holes"]])
print("parts: %d components, %d connector solid(s)" % (len(comps), len(conn)))
print("KiCad offset on J1:", [round(v, 3) for v in frame["kicad_offset_on_J1"]])
