#!/bin/sh
# Run the checker on the bundled examples.
# Run from the repo root: sh examples/run-example.sh
# The sample files each contain a failing pair, so the checker
# exits 1 on both — that is the expected result here.
set -e
cd "$(dirname "$0")/.."
echo "--- sample.css ---"
python3 src/colour_contrast_checker.py examples/sample.css || true
echo "--- pairs.txt ---"
python3 src/colour_contrast_checker.py --pairs examples/pairs.txt || true
echo "--- two hex colours (passing pair, exit 0) ---"
python3 src/colour_contrast_checker.py "#000000" "#ffffff"
