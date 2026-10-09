#!/bin/bash
#
# new-template.sh - Crée un nouveau projet à partir d'un template via degit,
# puis installe les dépendances npm.
#
# Usage: ./new-template.sh <template> <output-folder>
# Exemple: ./new-template.sh git@github.com:cegepvictoetienne/web3_prof/demonstrations/react/routeur_debut demo_routeur

set -e

TEMPLATE="$1"
OUTPUT="$2"

if [[ -z "$TEMPLATE" || -z "$OUTPUT" ]]; then
  echo "Usage: $0 <template> <output-folder>"
  echo "Exemple: $0 git@github.com:cegepvictoetienne/web3_prof/demonstrations/react/routeur_debut demo_routeur"
  exit 1
fi

if [[ -e "$OUTPUT" ]]; then
  echo "Erreur: le dossier '$OUTPUT' existe déjà."
  exit 1
fi

echo "Récupération du template '$TEMPLATE' dans '$OUTPUT'..."
npx degit "git@github.com:cegepvictoetienne/web3_prof/demonstrations/react/$TEMPLATE" "$OUTPUT"

cd "$OUTPUT"

echo "Installation des dépendances npm..."
npm install

echo "Terminé! Projet créé dans '$OUTPUT'."
