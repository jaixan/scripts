#!/bin/bash

  python3.13 -m venv venv
  source venv/bin/activate

  # Mise à jour de pip
  pip3.13 install --upgrade pip
  # Vérifie si package.json existe dans le sous-répertoire
  if [[ -f "requirements.txt" ]]; then
    echo "Liste des requis trouvé"
    pip3.13 install -r requirements.txt
  else
    echo "Pas de requirements.txt"
  fi

echo "Terminé!"
