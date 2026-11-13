#!/bin/sh
# Rebuilds the rvms_mini case from the board: STEP/GLB export (case models
# hidden), reference shapes, tray and cover, then the viewer page.
#   sh build.sh [board.kicad_pcb]
set -e
cd "$(dirname "$0")"
BOARD=${1:-../rvms_mini_v5.0.kicad_pcb}
KICAD=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
PRJ=$(cd "$(dirname "$BOARD")" && pwd)
mkdir -p build
python3 hide_case_models.py "$BOARD" build/board_nocase.kicad_pcb
"$KICAD" pcb export step -f -D KIPRJMOD="$PRJ" --subst-models -o build/board.step build/board_nocase.kicad_pcb
"$FC" extract_board.py
"$FC" build_case.py
"$KICAD" pcb export glb -f -D KIPRJMOD="$PRJ" --subst-models --cut-vias-in-body --include-pads \
  --include-silkscreen --include-soldermask -o build/board_raw.glb build/board_nocase.kicad_pcb
python3 export_board_glb.py build/board_raw.glb build/board.glb
python3 make_viewer.py
rm -rf __pycache__ rvms_mini_case.FCStd1
