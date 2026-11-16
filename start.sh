#!/bin/bash
# Botni ishga tushirish (macOS / Linux). Birinchi marta kutubxonalarni o'zi o'rnatadi.
cd "$(dirname "$0")"
if [ ! -d venv ]; then
  echo "📦 Kutubxonalar o'rnatilmoqda..."
  python3 -m venv venv
  ./venv/bin/pip install -q --upgrade pip
  ./venv/bin/pip install -q -r requirements.txt
fi
./venv/bin/python main.py
