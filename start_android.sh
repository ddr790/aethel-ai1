#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
command -v python >/dev/null 2>&1 || { pkg update -y; pkg install python -y; }
python start_aethel.py
