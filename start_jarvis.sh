#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
echo "Démarrage de J.A.R.V.I.S..."
./venv/bin/python main2.py
