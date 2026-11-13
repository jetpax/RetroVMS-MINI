# rvms_mini case: a tray and a cover for the v5.0 board, built around the
# board's own export (extract_board.py) and the real CKKB48 case's mounting.
# Run by build.sh (FreeCAD, headless, from this folder):
#
#   freecadcmd build_case.py
#
# Case frame (mm): z = 0 is the board's underside, +y the connector end; the
# centre and the ear positions are the real case's.
#
# Fixing: four M3 screws go up through the tray's standoffs and the board's
# mounting holes into heat-set inserts in posts under the lid, so the board is
# clamped between standoff and post and the lid top has no holes.
#
# Printing: the tray stands on its floor; the cover stands on its connector
# end (rvms_mini_cover.stl is laid that way), the hood at the bottom. In those
# orientations every surface rises at 45 degrees or steeper, the far end wall
# included (it slopes inside), so neither part needs support.

import json
import math
import os
import time

import FreeCAD as App
import MeshPart
import Part

V = App.Vector
HERE = os.getcwd()
B = os.path.join(HERE, "build")
T0 = time.time()


def log(*a):
    print("[%5.1fs]" % (time.time() - T0), *a, flush=True)


# ---- the real CKKB48 case (Corrected.STEP): mounting ears ----
EAR_HOLES = [(sx * 57.1, sy * 31.25) for sx in (-1, 1) for sy in (-1, 1)]
EAR_HOLE_D, EAR_R, EAR_T = 7.0, 6.6, 4.0

# ---- outline and walls ----
OUT_X = 46.6                 # half-width
OUT_Y0 = -56.25              # the end away from the connector
# the connector end is the connector's panel: the wall fills its neck, between
# the body on the board and the seal flange (found from the model, below)
NECK_GAP = (0.1, 0.06)       # body to wall, wall to flange
CORNER_R = 4.0
WALL = 2.9
FLOOR = 2.0                  # the floor sits CLR below the lowest part under the board
LID_T = 2.2
JOINT_Z = 0.25               # tray / cover split, just under the connector's neck
JOINT_GAP = 0.2              # the posts clamp the board, so the cover's edge stands clear
LIP_H, LIP_T, FIT = 2.5, 1.2, 0.25   # tray lip inside the cover's skirt
CLR = 0.8                    # over, beside and under components
RAMP_DEG = 45                # the lid's rise to the hood (45 or shallower prints on end)
NEAR_CONN = 10.0             # parts this close in front of the connector go under the hood

# ---- looks ----
BEVEL = 3.0                  # 45 degrees round the lid's top edge
HOOD_R = 4.0                 # round the hood's edges (inside: HOOD_R - LID_T)
LABEL = (0.5, 2.5, 3.0)      # label recess in the lid: depth, margin, corner radius

# ---- fixings ----
INSERT_D, INSERT_DEPTH = 4.0, 6.0     # M3 heat-set inserts, in the cover's posts
STANDOFF_D, POST_D = 9.0, 7.0
SCREW_D, HEAD_D, HEAD_DEPTH = 3.4, 6.5, 3.5   # M3 socket heads, sunk in the mounting face
BRIDGE_LAYER = 0.2           # print layer height: the counterbores' roofs bridge in two steps
GUSSET = 3.5

# ---- openings in the far end wall ----
CONN_GAP = 0.4               # around the connector's neck
# parts placed by footprint (board-file mm), so a frame shift carries them
J10_USB = dict(at=(98.81, 144.9), body=(8.94, 7.3), h=3.26)   # front at +3.65 toward the edge
J2_SD = dict(at=(64.23, 138.306416), front=5.7)               # card enters from the board edge
USB_OPEN = (13.0, 7.2, 3.0)  # w, h, corner r: room for a USB-C plug's grip
SD_OPEN = (13.0, 2.6, 1.0)


def load(name):
    s = Part.Shape()
    s.read(os.path.join(B, "ref_%s.brep" % name))
    return s


frame = json.load(open(os.path.join(B, "frame.json")))
TX, TY = frame["translate"][:2]
TH = frame["board_thickness"]
HOLES = frame["board_holes"]
board, conn, comps = (load(n) for n in ("board", "conn", "comps"))
cb = conn.BoundBox


def y_faces(shape, sign, min_width):
    """y of the planar faces facing +y (sign 1) or -y, at least min_width across."""
    out = []
    for f in shape.Faces:
        if f.Surface.__class__.__name__ == "Plane" and f.BoundBox.XLength >= min_width:
            n = f.normalAt(*f.ParameterRange[::2])
            if abs(n.y - sign) < 1e-6:
                out.append(f.BoundBox.YMin)
    return out


def width_at(shape, y):
    return max((w.BoundBox.XLength for w in shape.slice(V(0, 1, 0), y)), default=0)


# the connector's seal flange (about 56 wide) faces the board; its body (about
# 70 wide) ends ahead of it, found by bisecting slices: the wall goes between
flange_y = min(y for y in y_faces(conn, -1, 50) if y > cb.YMin + 10)
lo, hi = flange_y - 15, flange_y - 0.01
assert width_at(conn, lo) > 60 and width_at(conn, hi) < 60, "connector body not where expected"
for _ in range(25):
    mid = (lo + hi) / 2
    lo, hi = (mid, hi) if width_at(conn, mid) > 60 else (lo, mid)
body_y = hi
OUT_Y1 = flange_y - NECK_GAP[1]
IN_X, IN_Y0, IN_Y1 = OUT_X - WALL, OUT_Y0 + WALL, body_y + NECK_GAP[0]
log("connector: body face y %.2f, flange y %.2f: end wall %.2f thick" % (body_y, flange_y, OUT_Y1 - IN_Y1))


def case_xy(pcb_x, pcb_y):
    return pcb_x + TX, -pcb_y + TY


usb_x, usb_y = case_xy(*J10_USB["at"])
usb_front = usb_y - J10_USB["body"][1] / 2
usb_box = Part.makeBox(J10_USB["body"][0], J10_USB["body"][1], J10_USB["h"],
                       V(usb_x - J10_USB["body"][0] / 2, usb_front, TH))
usb_z = TH + J10_USB["h"] / 2
sd_x, sd_y = case_xy(*J2_SD["at"])
sd_z = TH + 1.0              # the card's mid-plane in the socket


# ---------------------------------------------------------------- helpers
def rbox(hx, y0, y1, r, z0, z1):
    """|x| <= hx, y0..y1, z0..z1, vertical edges rounded to r."""
    r = max(r, 0.05)
    s = Part.makeBox(2 * hx - 2 * r, y1 - y0, z1 - z0, V(-hx + r, y0, z0))
    s = s.fuse(Part.makeBox(2 * hx, y1 - y0 - 2 * r, z1 - z0, V(-hx, y0 + r, z0)))
    for cx in (-hx + r, hx - r):
        for cy in (y0 + r, y1 - r):
            s = s.fuse(Part.makeCylinder(r, z1 - z0, V(cx, cy, z0)))
    return s.removeSplitter()


def rrect_wire(hx, y0, y1, r, z):
    """The outline of rbox at height z, starting mid-way along the near side."""
    c = r * (1 - math.sqrt(0.5))
    P = lambda x, y: V(x, y, z)
    e = [Part.LineSegment(P(0, y0), P(hx - r, y0)),
         Part.Arc(P(hx - r, y0), P(hx - c, y0 + c), P(hx, y0 + r)),
         Part.LineSegment(P(hx, y0 + r), P(hx, y1 - r)),
         Part.Arc(P(hx, y1 - r), P(hx - c, y1 - c), P(hx - r, y1)),
         Part.LineSegment(P(hx - r, y1), P(-hx + r, y1)),
         Part.Arc(P(-hx + r, y1), P(-hx + c, y1 - c), P(-hx, y1 - r)),
         Part.LineSegment(P(-hx, y1 - r), P(-hx, y0 + r)),
         Part.Arc(P(-hx, y0 + r), P(-hx + c, y0 + c), P(-hx + r, y0)),
         Part.LineSegment(P(-hx + r, y0), P(0, y0))]
    return Part.Wire([s.toShape() for s in e])


def slab(z0, z1):
    return Part.makeBox(400, 400, z1 - z0, V(-200, -200, z0))


def xz_face(pts, y):
    return Part.Face(Part.makePolygon([V(x, y, z) for x, z in pts] + [V(pts[0][0], y, pts[0][1])]))


def rrect_xz(cx, cz, w, h, r, y):
    """A rounded rectangle in the plane y, centred (cx, cz)."""
    f = Part.Face(Part.makePolygon([V(cx - w / 2 + r, y, cz - h / 2), V(cx + w / 2 - r, y, cz - h / 2),
                                    V(cx + w / 2 - r, y, cz + h / 2), V(cx - w / 2 + r, y, cz + h / 2),
                                    V(cx - w / 2 + r, y, cz - h / 2)]))
    f = f.fuse(Part.Face(Part.makePolygon([V(cx - w / 2, y, cz - h / 2 + r), V(cx + w / 2, y, cz - h / 2 + r),
                                           V(cx + w / 2, y, cz + h / 2 - r), V(cx - w / 2, y, cz + h / 2 - r),
                                           V(cx - w / 2, y, cz - h / 2 + r)])))
    for ax in (cx - w / 2 + r, cx + w / 2 - r):
        for az in (cz - h / 2 + r, cz + h / 2 - r):
            f = f.fuse(Part.Face(Part.Wire(Part.makeCircle(r, V(ax, y, az), V(0, 1, 0)))))
    return f.removeSplitter()


def through_y(face, y0, y1):
    """Extrude a face lying in the plane y = y0 to y1."""
    return face.extrude(V(0, y1 - y0, 0))


def teardrop_z(cx, cy, r, z0, z1, toward):
    """Round along z with a 45-degree point toward +y (toward 1) or -y: printed
    on its side, the point is the part that builds over air."""
    circ = Part.Face(Part.Wire(Part.makeCircle(r, V(cx, cy, z0), V(0, 0, 1))))
    d = r / math.sqrt(2)
    tip = Part.Face(Part.makePolygon([V(cx - d, cy + toward * d, z0), V(cx, cy + toward * r * math.sqrt(2), z0),
                                      V(cx + d, cy + toward * d, z0), V(cx - d, cy + toward * d, z0)]))
    return circ.fuse(tip).removeSplitter().extrude(V(0, 0, z1 - z0))


def mesh_points(shape, defl=0.1):
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=defl, AngularDeflection=0.35, Relative=False)
    return [(p.x, p.y, p.z) for p in m.Points]


def slice_points(shape, y0, y1, step=0.5, dist=0.5):
    """Outline points of cross-sections every step along y: these sample the
    middle of large flat faces too, which a mesh's vertices do not."""
    pts, y = [], y0
    while y <= y1:
        for w in shape.slice(V(0, 1, 0), y):
            for e in w.Edges:
                pts += [(p.x, p.y, p.z) for p in e.discretize(Distance=dist)]
        y += step
    return pts


def fillet_away(shape, r, z_base, y_end):
    """Round the edges of a hood solid, except where it meets the lid (z_base)
    and its end face (y_end). The edges running down into the lid go first if
    the kernel refuses them."""
    flat = lambda e: e.BoundBox.ZMax < z_base + 1e-6 or e.BoundBox.YMin > y_end - 1e-6
    edges = [e for e in shape.Edges if not flat(e)]
    upper = [e for e in edges if e.BoundBox.ZMin > z_base + 1e-6]
    for pick, what in ((edges, "all edges"), (upper, "upper edges")):
        try:
            out = shape.makeFillet(r, pick)
            if out.isValid():
                return out, what
        except Exception:
            pass
    return shape, "none"


# ------------------------------------------- heights the case must clear
log("meshing the board's parts")
pts_comp = mesh_points(comps, 0.2) + [(v.X, v.Y, v.Z) for v in usb_box.Vertexes]
pts_conn = mesh_points(conn) + slice_points(conn, cb.YMin + 0.01, IN_Y1)
log("%d points" % (len(pts_comp) + len(pts_conn)))
inside = lambda p: IN_Y0 <= p[1] <= IN_Y1 and abs(p[0]) <= IN_X
near = lambda p: p[1] >= cb.YMin - NEAR_CONN and abs(p[0]) <= max(abs(cb.XMin), abs(cb.XMax))
# under the board: the floor clears the lowest part (the connector's pins)
floor_top = min(p[2] for p in pts_comp + pts_conn if inside(p)) - CLR
MOUNT_Z = floor_top - FLOOR
# the low lid clears everything away from the connector; the hood covers the rest
c_low = max(p[2] for p in pts_comp if inside(p) and not near(p)) + CLR
under_hood = [p for p in pts_comp + pts_conn if inside(p) and p[2] + CLR > c_low]
assert all(near(p) for p in under_hood), "a tall part away from the connector"
c_hood = max(p[2] for p in under_hood) + CLR
# hood cross-section: a trapezoid, half-width w0 at the lid's ceiling, w1 at its own
top_band = [p for p in under_hood if p[2] + CLR >= c_hood - 3]
w1 = max(abs(p[0]) for p in top_band) + CLR
w0 = w1
for x, y, z in under_hood:
    s = max(0.0, (z - c_low) / (c_hood - c_low))
    if s < 0.98:
        w0 = max(w0, (abs(x) + CLR - w1 * s) / (1 - s))
tan_r = math.tan(math.radians(RAMP_DEG))
y_r0 = min(y - (z + CLR - c_low) / tan_r for x, y, z in under_hood)
lid_top = c_low + LID_T
hood_top = c_hood + LID_T
log("floor top %.2f, mounting face %.2f; low lid: ceiling %.2f, top %.2f; hood: ceiling %.2f, top %.2f, "
    "half-width %.2f..%.2f, ramp from y %.2f" % (floor_top, MOUNT_Z, c_low, lid_top, c_hood, hood_top, w0, w1, y_r0))


def ramp_below(c, y_from):
    """Everything under the plane z = c + (y - y_from) * tan(RAMP), x unlimited."""
    ya, yb = -200.0, 200.0
    prof = Part.Face(Part.makePolygon([V(-200, ya, -100), V(-200, yb, -100),
                                       V(-200, yb, c + (yb - y_from) * tan_r),
                                       V(-200, ya, c + (ya - y_from) * tan_r), V(-200, ya, -100)]))
    return prof.extrude(V(400, 0, 0))


# the sides run on down below the lid's top, so at the connector end, where the
# lid's edge is bevelled, the hood still stands on the lid
xb = w0 + (BEVEL + 3) * (w0 - w1) / (c_hood - c_low)
hood_prof = [(-xb, c_low - BEVEL - 3), (xb, c_low - BEVEL - 3), (w1, c_hood), (-w1, c_hood)]
y_h0 = max(y_r0 - 30, IN_Y0 + 1)
hood_in = through_y(xz_face(hood_prof, y_h0), y_h0, IN_Y1).common(ramp_below(c_low, y_r0)).common(
    slab(c_low - 0.5, 200))
hood_in, how_in = fillet_away(hood_in, HOOD_R - LID_T, c_low - 0.5, IN_Y1)
hood_out = through_y(xz_face(hood_prof, y_h0).makeOffset2D(LID_T, join=2), y_h0, OUT_Y1).common(
    ramp_below(c_low + LID_T / math.cos(math.radians(RAMP_DEG)), y_r0)).common(slab(lid_top - BEVEL - 0.5, 200))
hood_out, how_out = fillet_away(hood_out, HOOD_R, lid_top - BEVEL - 0.5, OUT_Y1)
log("hood rounded: outside %s, inside %s" % (how_out, how_in))

# ------------------------------------------------------------------- body
lid_bevel = Part.makeLoft([rrect_wire(OUT_X, OUT_Y0, OUT_Y1, CORNER_R, lid_top - BEVEL),
                           rrect_wire(OUT_X - BEVEL, OUT_Y0 + BEVEL, OUT_Y1 - BEVEL, CORNER_R - BEVEL, lid_top)],
                          True, True)
outer = rbox(OUT_X, OUT_Y0, OUT_Y1, CORNER_R, MOUNT_Z, lid_top - BEVEL).fuse(lid_bevel).fuse(hood_out).removeSplitter()
cavity = rbox(IN_X, IN_Y0, IN_Y1, CORNER_R - WALL, floor_top, c_low).fuse(hood_in).removeSplitter()
body = outer.cut(cavity)
log("body built")
tray = body.common(slab(MOUNT_Z - 1, JOINT_Z))
cover = body.common(slab(JOINT_Z + JOINT_GAP, hood_top + 1))

# --------------------------------------------------------------- the tray
# the lip runs along the sides and the far end; the connector-end wall is too
# thin for one (the connector's flange covers that joint instead)
no_lip = Part.makeBox(400, 50, 50, V(-200, IN_Y1 - CORNER_R, JOINT_Z - 5))
lip = rbox(IN_X + LIP_T, IN_Y0 - LIP_T, IN_Y1 + LIP_T, CORNER_R - WALL + LIP_T, JOINT_Z, JOINT_Z + LIP_H).cut(
    rbox(IN_X, IN_Y0, IN_Y1, CORNER_R - WALL, JOINT_Z - 1, JOINT_Z + LIP_H + 1)).cut(no_lip)
adds = [lip]
for hx, hy in HOLES:                            # board standoffs
    adds.append(Part.makeCylinder(STANDOFF_D / 2, -floor_top, V(hx, hy, floor_top)))
for ex, ey in EAR_HOLES:                        # mounting ears and their gussets
    s = 1 if ex > 0 else -1
    x_wall = s * (OUT_X - 1)
    ear = Part.makeBox(abs(ex - x_wall), 2 * EAR_R, EAR_T, V(min(ex, x_wall), ey - EAR_R, MOUNT_Z))
    ear = ear.fuse(Part.makeCylinder(EAR_R, EAR_T, V(ex, ey, MOUNT_Z)))
    g = xz_face([(s * OUT_X - s * 0.5, MOUNT_Z + EAR_T), (s * (OUT_X + GUSSET), MOUNT_Z + EAR_T),
                 (s * OUT_X - s * 0.5, MOUNT_Z + EAR_T + GUSSET)], ey - 1.5)
    adds += [ear, through_y(g, ey - 1.5, ey + 1.5)]
for a in adds:
    tray = tray.fuse(a)
cuts = []
for hx, hy in HOLES:                            # screw up through the standoff, head sunk
    cuts.append(Part.makeCylinder(SCREW_D / 2, 2 - MOUNT_Z, V(hx, hy, MOUNT_Z - 1)))
    bore = Part.makeCylinder(HEAD_D / 2, HEAD_DEPTH + 1, V(hx, hy, MOUNT_Z - 1))
    cuts.append(bore)
    # the roof bridges in two layers, each anchored at both ends: first a slot
    # the screw's width right across the bore, then a square across the slot
    z0 = MOUNT_Z + HEAD_DEPTH
    slot = Part.makeBox(HEAD_D, SCREW_D, BRIDGE_LAYER, V(hx - HEAD_D / 2, hy - SCREW_D / 2, z0))
    cuts.append(slot.common(Part.makeCylinder(HEAD_D / 2, 1, V(hx, hy, z0 - 0.5))))
    cuts.append(Part.makeBox(SCREW_D, SCREW_D, BRIDGE_LAYER, V(hx - SCREW_D / 2, hy - SCREW_D / 2, z0 + BRIDGE_LAYER)))
for ex, ey in EAR_HOLES:
    cuts.append(Part.makeCylinder(EAR_HOLE_D / 2, EAR_T + 2, V(ex, ey, MOUNT_Z - 1)))
cuts.append(through_y(rrect_xz(usb_x, usb_z, *USB_OPEN, OUT_Y0 - 1), OUT_Y0 - 1, IN_Y0 + 1))
for c in cuts:
    tray = tray.cut(c)
tray = tray.removeSplitter()
log("tray built")

# -------------------------------------------------------------- the cover
# Standing on its connector end, the cover builds toward the far end, so that
# wall is its last, overhead layer: inside it slopes down from the lid at 45
# degrees, so it builds up rather than spans
reach = c_low - JOINT_Z
end_slope = Part.Face(Part.makePolygon([V(-IN_X - 1, IN_Y0 - 1, JOINT_Z - 1), V(-IN_X - 1, IN_Y0 + reach + 0.5, c_low + 0.5),
                                        V(-IN_X - 1, IN_Y0 - 1, c_low + 0.5), V(-IN_X - 1, IN_Y0 - 1, JOINT_Z - 1)]))
end_slope = end_slope.extrude(V(2 * IN_X + 2, 0, 0)).common(
    rbox(IN_X + 0.5, IN_Y0 - 0.5, IN_Y1, max(CORNER_R - WALL, 0.1), JOINT_Z + JOINT_GAP, c_low + 0.5))
cover = cover.fuse(end_slope)
# posts down onto the board round its mounting holes, pointed toward the
# connector end (overhead when printed), holding the screws' inserts
for hx, hy in HOLES:
    post = teardrop_z(hx, hy, POST_D / 2, TH, lid_top, 1)
    cover = cover.fuse(post.common(outer))
# parts on the board beside a post: the post steps round them, CLR clear
post_keepouts = []
for s in comps.Solids:
    b = s.BoundBox
    if b.ZMax > TH and any(b.XMax > hx - POST_D / 2 - CLR - 1 and b.XMin < hx + POST_D / 2 + CLR + 1
                           and b.YMax > hy - POST_D / 2 - CLR - 1 and b.YMin < hy + POST_D * 0.71 + CLR + 1
                           for hx, hy in HOLES):
        top = min(b.ZMax + CLR, c_low - 0.01)
        bottom = TH - 0.01 if b.ZMin < TH + 1 else b.ZMin    # parts on the board: down to it
        post_keepouts.append(Part.makeBox(b.XLength + 2 * CLR, b.YLength + 2 * CLR, top - bottom,
                                          V(b.XMin - CLR, b.YMin - CLR, bottom)))
log("%d parts beside the posts" % len(post_keepouts))
# the connector's neck passes through the cover's end wall: its outline in the
# middle of the wall, with a gap, open at the bottom so the cover drops on
faces = [Part.Face(w) for w in conn.slice(V(0, 1, 0), (IN_Y1 + OUT_Y1) / 2) if w.isClosed()]
neck = Part.Face(max(faces, key=lambda f: f.Area).OuterWire).makeOffset2D(CONN_GAP, join=0)
neck.translate(V(0, IN_Y1 - 1 - neck.BoundBox.YMin, 0))
nb = neck.BoundBox
low = neck.common(xz_face([(-200, nb.ZMin - 1), (200, nb.ZMin - 1), (200, nb.ZMin + 1.0),
                           (-200, nb.ZMin + 1.0)], IN_Y1 - 1)).BoundBox
open_face = neck.fuse(xz_face([(low.XMin, JOINT_Z - 3), (low.XMax, JOINT_Z - 3),
                               (low.XMax, nb.ZMin + 1.0), (low.XMin, nb.ZMin + 1.0)], IN_Y1 - 1)).removeSplitter()
label_y1 = y_r0 - LID_T * (math.sqrt(2) - 1) - LABEL[1]
lx, ly0 = OUT_X - BEVEL - LABEL[1], OUT_Y0 + BEVEL + LABEL[1]
cuts = [through_y(open_face, IN_Y1 - 1, OUT_Y1 + 1),
        rbox(IN_X + LIP_T + FIT, IN_Y0 - LIP_T - FIT, IN_Y1 + LIP_T + FIT, CORNER_R - WALL + LIP_T + FIT,
             JOINT_Z - 1, JOINT_Z + LIP_H + FIT).cut(
            rbox(IN_X - FIT, IN_Y0 + FIT, IN_Y1 - FIT, max(CORNER_R - WALL - FIT, 0.1), JOINT_Z - 2, JOINT_Z + LIP_H + 2)
        ).cut(no_lip),
        through_y(rrect_xz(usb_x, usb_z, *USB_OPEN, OUT_Y0 - 1), OUT_Y0 - 1, IN_Y0 + reach + 1),
        through_y(rrect_xz(sd_x, sd_z, *SD_OPEN, OUT_Y0 - 1), OUT_Y0 - 1, IN_Y0 + reach + 1),
        rbox(lx, ly0, label_y1, LABEL[2], lid_top - LABEL[0], lid_top + 1)]
for hx, hy in HOLES:                            # inserts, from below
    cuts.append(teardrop_z(hx, hy, INSERT_D / 2, TH - 1, TH + INSERT_DEPTH, -1))
cuts += post_keepouts
for c in cuts:
    cover = cover.cut(c)
cover = cover.removeSplitter()
log("cover built")

# ------------------------------------------------------------------ checks
log("checking")
log("tray: valid %s, solids %d, %.1f cm3" % (tray.isValid(), len(tray.Solids), tray.Volume / 1000))
log("cover: valid %s, solids %d, %.1f cm3" % (cover.isValid(), len(cover.Solids), cover.Volume / 1000))
log("tray-cover overlap %.3f mm3, gap %.2f" % (tray.common(cover).Volume, tray.distToShape(cover)[0]))
for name, ref in (("board", board), ("connector", conn), ("USB-C", usb_box)):
    log("  %-9s in tray %.3f mm3, in cover %.3f mm3; gap to tray %.2f, to cover %.2f"
        % (name, tray.common(ref).Volume, cover.common(ref).Volume, tray.distToShape(ref)[0], cover.distToShape(ref)[0]))


def near_part(sh, part):
    """Parts whose box comes within 1 mm of the part's box: worth an exact check."""
    a, b = sh.BoundBox, part.BoundBox
    return a.XMax > b.XMin - 1 and a.XMin < b.XMax + 1 and a.YMax > b.YMin - 1 and a.YMin < b.YMax + 1 \
        and a.ZMax > b.ZMin - 1 and a.ZMin < b.ZMax + 1


# the parts that could touch: near the lid's ceiling, the floor, the walls, or a post or standoff
def candidate(sh):
    b = sh.BoundBox
    if b.ZMax > c_low - CLR - 0.5 or b.ZMin < floor_top + CLR + 0.5:
        return True
    if b.XMin < -IN_X + 2 or b.XMax > IN_X - 2 or b.YMin < IN_Y0 + 9 or b.YMax > IN_Y1 - 2:
        return True
    return any(b.XMax > x - 8 and b.XMin < x + 8 and b.YMax > y - 8 and b.YMin < y + 8 for x, y in HOLES)


cands = [s for s in comps.Solids if candidate(s)]
worst = dict(tray=99, cover=99)
hits = 0
for s in cands:
    for name, part in (("tray", tray), ("cover", cover)):
        if near_part(s, part):
            d = part.distToShape(s)[0]
            worst[name] = min(worst[name], d)
            if d < 1e-6 and part.common(s).Volume > 1e-3:
                hits += 1
log("  parts: %d of %d checked exactly, %d overlap; closest to the tray %.2f mm, to the cover %.2f mm"
    % (len(cands), len(comps.Solids), hits, worst["tray"], worst["cover"]))
log("overall: %.1f x %.1f, mounting face to hood top %.1f mm (to the lid top %.1f)"
    % (tray.BoundBox.XLength, OUT_Y1 - OUT_Y0, hood_top - MOUNT_Z, lid_top - MOUNT_Z))
screw = -MOUNT_Z - HEAD_DEPTH + TH + INSERT_DEPTH - 0.5
log("screws: head seat to the end of the insert %.1f mm, so M3 x %d" % (screw, int(screw // 2 * 2)))

# ----------------------------------------------------------------- outputs
OUTN = "rvms_mini"
Part.makeCompound([tray, cover]).exportStep(os.path.join(HERE, OUTN + "_case.step"))
tray.exportStep(os.path.join(HERE, OUTN + "_tray.step"))
cover.exportStep(os.path.join(HERE, OUTN + "_cover.step"))


def write_stl(shape, path):
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05, AngularDeflection=0.2, Relative=False)
    m.write(path)
    ok = m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections()
    log("%s: %d facets, clean %s" % (os.path.basename(path), m.CountFacets, ok))


# assembly frame (viewer, KiCad), then print orientation
write_stl(tray, os.path.join(B, "tray.stl"))
write_stl(cover, os.path.join(B, "cover.stl"))
t = tray.copy()
t.translate(V(0, 0, -MOUNT_Z))
write_stl(t, os.path.join(HERE, OUTN + "_tray.stl"))
c = cover.copy()
c.rotate(V(0, 0, 0), V(1, 0, 0), -90)         # connector end down
c.translate(V(0, 0, -c.BoundBox.ZMin))
write_stl(c, os.path.join(HERE, OUTN + "_cover.stl"))

doc = App.newDocument("rvms_mini_case")
for name, shape in (("Tray", tray), ("Cover", cover)):
    src = doc.addObject("Part::Feature", name + "_solid")
    src.Shape = shape
    body = doc.addObject("PartDesign::Body", name)
    body.BaseFeature = src
ref = doc.addObject("Part::Feature", "Board_reference")
ref.Shape = Part.makeCompound([board, conn])
doc.recompute()
for obj in doc.Objects:
    if obj.Name in ("Tray_solid", "Cover_solid", "Board_reference") or obj.TypeId in ("App::Line", "App::Plane", "App::Point"):
        obj.Visibility = False
doc.saveAs(os.path.join(HERE, OUTN + "_case.FCStd"))
json.dump(dict(low_lid_ceiling=c_low, lid_top=lid_top, hood_ceiling=c_hood, hood_top=hood_top,
               hood_half_width=[w0, w1], ramp_start_y=y_r0, mount_z=MOUNT_Z, joint_z=JOINT_Z,
               screw_length=int(screw // 2 * 2), bevel=BEVEL, label=[2 * lx, label_y1 - ly0],
               kicad_offset_on_J1=frame["kicad_offset_on_J1"]),
          open(os.path.join(B, "case.json"), "w"), indent=1)
log("KiCad: add %s_case.step to J1, offset %s, rotation 0" % (OUTN, [round(v, 3) for v in frame["kicad_offset_on_J1"]]))
