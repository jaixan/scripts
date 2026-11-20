#!/bin/bash
#
# Restauration du backup restic du cégep (voir backup-cegep-restic.sh) sur un nouveau Mac.
#
# Usage : ./restore-cegep-restic.sh [options]
#   --snapshot ID   snapshot à restaurer (défaut : latest, tag cegep)
#   --target DIR    dossier de destination (défaut : $HOME)
#   --dry-run       montre ce qui serait restauré sans rien écrire
#   --with-cloud    restaure aussi OneDrive et iCloud/Obsidian, dans $HOME/restic-restore-cloud
#                   (jamais directement dans les dossiers gérés par OneDrive/iCloud)
#   --brew          réinstalle les paquets Homebrew du Brewfile (formules, casks, taps, App Store,
#                   VS Code), ou de homebrew-installed-packages.txt pour les anciens snapshots
#   --list          liste les snapshots et quitte
#
# Les chemins sont stockés en absolu dans le dépôt (/Users/<ancien>/...). Le script détecte
# l'ancien dossier personnel et restaure son contenu dans le nouveau $HOME, même si le nom
# d'utilisateur a changé. Surcharge possible avec OLD_HOME=/Users/xxx.
#
# Identifiants : lus dans le trousseau (mêmes entrées que le script de backup). S'ils
# n'existent pas encore (nouveau Mac), ils sont demandés puis enregistrés dans le trousseau.

set -o pipefail

SNAPSHOT="latest"
TARGET="$HOME"
DRY_RUN=""
WITH_CLOUD=""
WITH_BREW=""
LIST_ONLY=""

while [ $# -gt 0 ]; do
    case "$1" in
        --snapshot)   SNAPSHOT="$2"; shift 2 ;;
        --target)     TARGET="$2"; shift 2 ;;
        --dry-run)    DRY_RUN=1; shift ;;
        --with-cloud) WITH_CLOUD=1; shift ;;
        --brew)       WITH_BREW=1; shift ;;
        --list)       LIST_ONLY=1; shift ;;
        -h|--help)    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Option inconnue : $1" >&2; exit 1 ;;
    esac
done

LOG="$HOME/Library/Logs/restore-cegep-restic.log"
mkdir -p "$(dirname "$LOG")"
echo "=== $(date) ===" >> "$LOG"

err() { printf "\033[31m%s\033[0m\n" "$*" >&2; }
title() { printf "\n\033[1m%s\033[0m\n" "$*"; }

# --- restic ---------------------------------------------------------------
if ! command -v restic > /dev/null; then
    if command -v brew > /dev/null; then
        title "Installation de restic"
        brew install restic || exit 1
    else
        err "restic introuvable. Installer Homebrew (https://brew.sh) puis : brew install restic"
        exit 1
    fi
fi

# --- identifiants (trousseau, sinon demandés puis enregistrés) --------------
keychain_get() {
    security find-generic-password -a "$USER" -s "$1" -w 2>/dev/null
}

keychain_ensure() {
    local service="$1" label="$2" value
    value="$(keychain_get "$service")"
    if [ -z "$value" ]; then
        read -r -s -p "$label : " value; echo >&2
        [ -z "$value" ] && { err "Valeur vide pour $label"; exit 1; }
        security add-generic-password -U -a "$USER" -s "$service" -w "$value" \
            || { err "Impossible d'enregistrer $service dans le trousseau"; exit 1; }
        echo "→ enregistré dans le trousseau ($service)" >&2
    fi
}

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$RESTIC_PASSWORD_COMMAND$RESTIC_PASSWORD" ]; then
    title "Identifiants"
fi
[ -z "$RESTIC_PASSWORD_COMMAND$RESTIC_PASSWORD" ] && keychain_ensure restic-cegep "Mot de passe du dépôt restic"
[ -z "$AWS_ACCESS_KEY_ID" ]     && keychain_ensure restic-cegep-aws-key-id "AWS access key ID (eazybackup)"
[ -z "$AWS_SECRET_ACCESS_KEY" ] && keychain_ensure restic-cegep-aws-secret "AWS secret access key (eazybackup)"

export RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-s3:https://s3.ca-central-1.eazybackup.com/maccegep}"
if [ -z "$RESTIC_PASSWORD" ]; then
    export RESTIC_PASSWORD_COMMAND="${RESTIC_PASSWORD_COMMAND:-security find-generic-password -a $USER -s restic-cegep -w}"
fi
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(keychain_get restic-cegep-aws-key-id)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(keychain_get restic-cegep-aws-secret)}"

title "Connexion au dépôt $RESTIC_REPOSITORY"
if ! restic cat config > /dev/null 2>>"$LOG"; then
    err "Impossible d'ouvrir le dépôt (mot de passe ou clés S3 invalides ? voir $LOG)"
    exit 1
fi

if [ -n "$LIST_ONLY" ]; then
    restic snapshots --tag cegep
    exit $?
fi

# --- snapshot et ancien $HOME ----------------------------------------------
snap_args=()
[ "$SNAPSHOT" = "latest" ] && snap_args=(--tag cegep)

snap_json="$(restic snapshots "${snap_args[@]}" --json "$SNAPSHOT" 2>>"$LOG")"
snap_id="$(printf '%s' "$snap_json" | grep -o '"short_id":"[^"]*"' | head -1 | cut -d'"' -f4)"
snap_time="$(printf '%s' "$snap_json" | grep -o '"time":"[^"]*"' | head -1 | cut -d'"' -f4)"
if [ -z "$snap_id" ]; then
    err "Snapshot « $SNAPSHOT » introuvable."
    exit 1
fi

if [ -z "$OLD_HOME" ]; then
    first_path="$(printf '%s' "$snap_json" | grep -o '"paths":\["[^"]*"' | head -1 | sed 's/.*\["//; s/"$//')"
    OLD_HOME="$(printf '%s' "$first_path" | cut -d/ -f1-3)"   # /Users/<nom>
fi
if [[ "$OLD_HOME" != /Users/* ]]; then
    err "Impossible de déterminer l'ancien dossier personnel (trouvé : « $OLD_HOME »). Utiliser OLD_HOME=/Users/xxx."
    exit 1
fi

title "Snapshot $snap_id ($snap_time)"
echo "  Source      : $OLD_HOME"
echo "  Destination : $TARGET"
[ -n "$DRY_RUN" ]    && echo "  Mode        : dry-run (aucune écriture)"
[ -n "$WITH_CLOUD" ] && echo "  Cloud       : OneDrive + iCloud → $HOME/restic-restore-cloud"

if [ -z "$DRY_RUN" ]; then
    echo
    echo "Les fichiers existants dans la destination seront écrasés s'ils diffèrent."
    read -r -p "Continuer ? [o/N] " answer
    [[ "$answer" =~ ^[oOyY]$ ]] || { echo "Annulé."; exit 0; }
fi

restore_opts=(--overwrite if-changed)
[ -n "$DRY_RUN" ] && restore_opts+=(--dry-run -v)

# --- restauration principale (sans les dossiers gérés par OneDrive/iCloud) ---
title "Restauration des fichiers"
mkdir -p "$TARGET"
restic restore "$snap_id:$OLD_HOME" --target "$TARGET" "${restore_opts[@]}" \
    --exclude "CloudStorage" \
    --exclude "Mobile Documents" \
    2>>"$LOG" || { err "Échec de la restauration (voir $LOG)"; exit 1; }

# --- dossiers cloud, à part -------------------------------------------------
if [ -n "$WITH_CLOUD" ]; then
    CLOUD_DIR="$HOME/restic-restore-cloud"
    title "Restauration OneDrive + iCloud dans $CLOUD_DIR"
    [ -z "$DRY_RUN" ] && mkdir -p "$CLOUD_DIR"
    restic restore "$snap_id:$OLD_HOME/Library" --target "$CLOUD_DIR" "${restore_opts[@]}" \
        --include "CloudStorage" \
        --include "Mobile Documents" \
        2>>"$LOG" || { err "Échec de la restauration cloud (voir $LOG)"; exit 1; }
    echo "À déplacer manuellement une fois OneDrive / iCloud configurés."
fi

[ -n "$DRY_RUN" ] && { printf "\n\033[32mDry-run terminé.\033[0m\n"; exit 0; }

# --- permissions SSH --------------------------------------------------------
if [ -d "$TARGET/.ssh" ]; then
    title "Permissions de ~/.ssh"
    chmod 700 "$TARGET/.ssh"
    find "$TARGET/.ssh" -type f ! -name '*.pub' ! -name 'known_hosts*' ! -name 'config' -exec chmod 600 {} +
fi

# --- Homebrew ---------------------------------------------------------------
BREWFILE="$TARGET/Brewfile"
BREW_LIST="$TARGET/homebrew-installed-packages.txt"   # format des anciens snapshots
if [ -n "$WITH_BREW" ]; then
    title "Réinstallation des paquets Homebrew"
    if ! command -v brew > /dev/null; then
        err "Homebrew n'est pas installé (https://brew.sh)."
    elif [ -f "$BREWFILE" ]; then
        # Les apps App Store exigent d'être connecté à l'App Store; les extensions VS Code, la commande « code ».
        brew bundle install --file="$BREWFILE" 2>>"$LOG" \
            || err "Certains paquets ont échoué (voir $LOG; relancer : brew bundle install --file=$BREWFILE)"
    elif [ ! -f "$BREW_LIST" ]; then
        err "Ni $BREWFILE ni $BREW_LIST introuvable."
    else
        echo "Pas de Brewfile (ancien snapshot) : formules seulement, depuis $BREW_LIST"
        # Les lignes sans indentation de l'arbre « brew deps --tree » sont les formules installées
        # (les dépendances sont réinstallées automatiquement).
        formulas=()
        while IFS= read -r line; do formulas+=("$line"); done \
            < <(grep -E '^[A-Za-z0-9@._+/-]+$' "$BREW_LIST" | sort -u)
        echo "${#formulas[@]} formules : ${formulas[*]}"
        brew install "${formulas[@]}" 2>>"$LOG" || err "Certaines formules ont échoué (voir $LOG)"
    fi
elif [ -f "$BREWFILE" ] || [ -f "$BREW_LIST" ]; then
    echo
    echo "Astuce : relancer avec --brew pour réinstaller les paquets Homebrew."
fi

printf "\n\033[32mRestauration terminée!\033[0m\n"
echo "Le backup (backup-cegep-restic.sh) peut maintenant être utilisé : les identifiants sont dans le trousseau."
