#!/bin/bash
# usage: run.sh <prefix> <samples> <w> <h> view...
SP=$(cd "$(dirname "$0")/.." && pwd); P=$1; S=$2; W=$3; H=$4; shift 4
for v in "$@"; do
  a=$(python3 -c "import json;d=json.load(open('$SP/render/views.json'))['$v'];d.setdefault('exposure',-0.25);d.update(sp='$SP',samples=$S,res=[$W,$H],out='$SP/render/${P}_$v.jpg');print(json.dumps(d))")
  "$SP/bl/bin/python" "$SP/render/scene.py" -- "$a" 2>&1 | grep -E "DONE|Error|Traceback"
done
