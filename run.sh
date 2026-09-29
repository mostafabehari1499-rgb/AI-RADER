#!/usr/bin/env bash
# AI RADAR local run (Linux/macOS).
set -e
pip install -r requirements.txt
python -m engine.main "$@"
