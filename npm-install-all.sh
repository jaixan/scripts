#!/bin/bash

# Faire le tour de tous les sous-répertoires
for dir in */ ; do
  # Vérifie si package.json existe dans le sous-répertoire
  if [[ -f "$dir/package.json" ]]; then
    echo "Entrer dans : $dir"
    cd "$dir" || continue

    # Exécuter npm install
    echo "Installer les dépendances dans $dir..."
    npm install

    # Retour au dossier parent
    cd ..
  else
    echo "Pas de package.json dans $dir. Passons au suivant..."
  fi
done

echo "Terminé!"
