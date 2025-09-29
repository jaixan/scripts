#!/bin/bash

# Faire le tour de tous les sous-répertoires
for dir in */ ; do
  # Vérifie si package.json existe dans le sous-répertoire
  if [[ -f "$dir/package.json" ]]; then
    echo "Entrer dans : $dir"
    cd "$dir" || continue

    # Exécuter npm install
    mr --config=../.mrconfig register

    # Retour au dossier parent
    cd ..
  else
    echo "Pas de package.json dans $dir. Passons au suivant..."
  fi
done

echo "Terminé!"
