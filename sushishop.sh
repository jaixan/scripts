#!/bin/bash
# Ouvre un tunnel SSH vers un service de olive.profinfo.ca et l'affiche dans Chrome.
# Usage : ./sushishop.sh <service>     (sans paramètre : liste les services)
# Les services sont lus dans sushishop-services (format : port,nom).
# Le tunnel reste ouvert jusqu'à Ctrl+C.
set -euo pipefail

REMOTE="root@olive.profinfo.ca"
SERVICES="$(cd "$(dirname "$0")" && pwd -P)/sushishop-services"

if [[ ! -r "$SERVICES" ]]; then
  echo "Erreur : fichier introuvable : $SERVICES" >&2
  exit 1
fi

list_services() {
  echo "Services disponibles :"
  awk -F, 'NF >= 2 { sub(/\r$/, ""); printf "  %-24s %s\n", $2, $1 }' "$SERVICES"
}

if [[ $# -ne 1 || -z "$1" ]]; then
  { echo "Usage : $(basename "$0") <service>"; list_services; } >&2
  exit 1
fi

# 1. Port du service (nom exact, sans tenir compte de la casse)
PORT="$(NAME="$1" awk -F, '
  { sub(/\r$/, ""); gsub(/^[ \t]+|[ \t]+$/, "", $1); gsub(/^[ \t]+|[ \t]+$/, "", $2) }
  tolower($2) == tolower(ENVIRON["NAME"]) && $2 != "" { print $1; exit }
' "$SERVICES")"

if [[ -z "$PORT" ]]; then
  { echo "Erreur : service inconnu : $1"; list_services; } >&2
  exit 1
fi
if [[ ! "$PORT" =~ ^[0-9]+$ ]]; then
  echo "Erreur : port invalide pour $1 : $PORT" >&2
  exit 1
fi

# 2. Port local : le même que le service, sinon le prochain port libre
#    (macOS réserve les ports < 1024 à root : on ajoute 8000, ex. 88 → 8088)
LOCAL_PORT="$PORT"
if (( PORT < 1024 )); then
  LOCAL_PORT=$((PORT + 8000))
fi
while lsof -nP -iTCP:"$LOCAL_PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  LOCAL_PORT=$((LOCAL_PORT + 1))
done
if [[ "$LOCAL_PORT" != "$PORT" ]]; then
  echo "⚠︎ Le port local $PORT n'est pas disponible, utilisation de $LOCAL_PORT."
fi

# 3. Tunnel ; ssh ouvre Chrome (LocalCommand) une fois connecté et authentifié
URL="http://localhost:$LOCAL_PORT"
echo "→ $1 : $URL → $REMOTE:$PORT (Ctrl+C pour fermer le tunnel)"
exec ssh -N \
  -L "$LOCAL_PORT:localhost:$PORT" \
  -o ExitOnForwardFailure=yes \
  -o ConnectTimeout=10 \
  -o ServerAliveInterval=30 \
  -o ControlPath=none \
  -o PermitLocalCommand=yes \
  -o LocalCommand="open -a 'Google Chrome' '$URL'" \
  "$REMOTE"
