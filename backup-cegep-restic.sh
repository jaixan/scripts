#!/bin/bash
#
# Backup du cégep avec restic (équivalent de backup-cegep.sh).
#
# Première utilisation : stocker le mot de passe du dépôt dans le trousseau macOS
#   security add-generic-password -a "$USER" -s restic-cegep -w
# ainsi que les clés S3 (eazybackup) :
#   security add-generic-password -a "$USER" -s restic-cegep-aws-key-id -w
#   security add-generic-password -a "$USER" -s restic-cegep-aws-secret -w
# Le dépôt est initialisé automatiquement s'il n'existe pas.
#
# Variables surchargeables :
#   RESTIC_REPOSITORY        (défaut : S3 eazybackup, bucket maccegep)
#   RESTIC_PASSWORD_COMMAND  (défaut : lecture dans le trousseau)
#   AWS_ACCESS_KEY_ID        (défaut : lecture dans le trousseau)
#   AWS_SECRET_ACCESS_KEY    (défaut : lecture dans le trousseau)
#   SKIP_PRUNE=1             pour sauter forget/prune

set -o pipefail

export RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-s3:https://s3.ca-central-1.eazybackup.com/maccegep}"
export RESTIC_PASSWORD_COMMAND="${RESTIC_PASSWORD_COMMAND:-security find-generic-password -a $USER -s restic-cegep -w}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(security find-generic-password -a "$USER" -s restic-cegep-aws-key-id -w)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(security find-generic-password -a "$USER" -s restic-cegep-aws-secret -w)}"

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Clés S3 introuvables dans le trousseau (voir l'en-tête du script)." >&2
    exit 1
fi

ONEDRIVE="$HOME/Library/CloudStorage/OneDrive-CégepdeVictoriaville"
DROPBOX_KP="$HOME/Library/CloudStorage/Dropbox/keepass_perso"
LOG="$HOME/Library/Logs/backup-cegep-restic.log"

paths=(
    "$HOME/Documents"
    "$HOME/keys"
    "$ONEDRIVE/CegepVicto"
    "$ONEDRIVE/Administration"
    "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents"
    "$HOME/notes_de_cours"
    "$HOME/projets"
    "$HOME/demo_cours"
    "$HOME/.aliases"
    "$HOME/.mrconfig"
    "$HOME/.ssh"
    "$HOME/scripts"
    "$HOME/Library/Application Support/Code/User/settings.json"
    "$HOME/homebrew-installed-packages.txt"
)

# Exclusions globales (comme pour tous les rsync)
excludes=(
    --exclude=".DS_Store"
    --exclude=".next"
    --exclude="node_modules"
)

# Exclusions supplémentaires limitées à certains dossiers (comme dans backup-cegep.sh)
for dir in notes_de_cours projets demo_cours scripts; do
    for pat in .git venv sites www; do
        excludes+=(--exclude="$HOME/$dir/**/$pat")
    done
done

steps=(
    'Liste des paquets Homebrew'
    'Sauvegarde restic'
    'Nettoyage des anciens snapshots'
    'Fichier bidon pour Dropbox'
    'FantasSecrets.kdbx sur Dropbox'
)

step=0
total=${#steps[@]}

run_step() {
    ((step++))
    printf "\n\033[1m[%d/%d] %s\033[0m\n" "$step" "$total" "${steps[$step - 1]}"
    if ! "$@"; then
        printf "\033[31mErreur : l'étape « %s » a échoué (voir %s)\033[0m\n" "${steps[$step - 1]}" "$LOG"
        exit 1
    fi
}

brew_list() {
    brew deps --tree --installed > "$HOME/homebrew-installed-packages.txt" 2>>"$LOG"
}

restic_backup() {
    # Initialise le dépôt s'il n'existe pas encore
    if ! restic cat config > /dev/null 2>&1; then
        echo "Initialisation du dépôt $RESTIC_REPOSITORY"
        restic init 2>>"$LOG" || return 1
    fi
    restic backup --tag cegep "${excludes[@]}" "${paths[@]}" 2>>"$LOG"
}

restic_prune() {
    if [ -n "$SKIP_PRUNE" ]; then
        echo "Ignoré (SKIP_PRUNE)"
        return 0
    fi
    restic forget --tag cegep --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune 2>>"$LOG"
}

fetch_bookmarks() {
    rsync -ah "$REMOTE:/mnt/blockstorage/coffre/bookmarks.xbel" \
        "$HOME/notes_de_cours/bm/template/bookmarks.xbel" 2>>"$LOG"
}

generate_markdown() {
    (cd "$HOME/notes_de_cours/bm/" && ./xbel2md.py) > /dev/null 2>>"$LOG"
}

touch_dropbox() {
    date > "$DROPBOX_KP/current_date.txt"
}

fetch_keepass() {
    rsync -ah "$REMOTE:/mnt/blockstorage/coffre/FantasSecrets.kdbx" "$DROPBOX_KP/" 2>>"$LOG"
}

echo "=== $(date) ===" >> "$LOG"

run_step brew_list
run_step restic_backup
run_step restic_prune
run_step touch_dropbox
run_step fetch_keepass

printf "\n\033[32mBackup terminé!\033[0m\n"
