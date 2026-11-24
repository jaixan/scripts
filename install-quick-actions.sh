#!/bin/bash
# Installe les 3 Quick Actions (PDF / PowerPoint / Détecter IA depuis ZIP).
# Les workflows appellent $HOME/scripts/.venv/bin/python : ce repo doit donc être à ~/scripts.
set -euo pipefail

DIR="$HOME/scripts"
SERVICES="$HOME/Library/Services"

# 1. Le repo doit être à ~/scripts
HERE="$(cd "$(dirname "$0")" && pwd -P)"
if [[ "$HERE" != "$(cd "$DIR" 2>/dev/null && pwd -P)" ]]; then
  echo "Erreur : ce script doit être dans $DIR (actuellement : $HERE)." >&2
  echo "Les workflows utilisent ce chemin en dur." >&2
  exit 1
fi
cd "$DIR"

# 2. Environnement Python
PY="$(command -v python3.13 || command -v python3 || true)"
if [[ -z "$PY" ]]; then
  echo "Erreur : python3 introuvable. Installe-le (ex. brew install python@3.13)." >&2
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  echo "→ Création de .venv avec $PY"
  "$PY" -m venv .venv
fi
echo "→ Installation des dépendances"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

# 3. swiftc (pour l'OCR de « Détecter IA dans ZIP »)
if command -v swiftc >/dev/null 2>&1; then
  echo "→ Compilation de l'OCR"
  mkdir -p .build
  swiftc -O ocr.swift -o .build/ocr
else
  echo "⚠︎ swiftc introuvable : lance « xcode-select --install », puis relance ce script."
  echo "  (Seul « Détecter IA dans ZIP » en a besoin.)"
fi

# 4. Copie des workflows
mkdir -p "$SERVICES"
for wf in *.workflow; do
  echo "→ Installation de « ${wf%.workflow} »"
  rm -rf "$SERVICES/$wf"
  cp -R "$wf" "$SERVICES/"
done

# 5. Rafraîchir le menu Services
/System/Library/CoreServices/pbs -update 2>/dev/null || true
killall Finder 2>/dev/null || true

echo
echo "Terminé ! Clic droit sur un .zip → Actions rapides."
echo "S'il en manque une : Réglages Système → Clavier → Raccourcis clavier → Services → Fichiers et dossiers."
