#!/bin/zsh

rsync -ahP ~/Documents etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP /Users/etiennerivard/Library/CloudStorage/Dropbox etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP /Users/etiennerivard/Library/CloudStorage/OneDrive-CégepdeVictoriaville/CegepVicto etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/notes_de_cours etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/projets etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/demo_cours etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP ~/.aliases etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP ~/.mrconfig etienne@192.168.2.38:/home/etienne/mac-backup/
rsync -ahP ~/.ssh etienne@192.168.2.38:/home/etienne/mac-backup/

~/scripts/generate-vscode-extensions-install.sh
rsync -ahP --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/scripts etienne@192.168.2.38:/home/etienne/mac-backup/

rsync -ahP ~/Library/Application\ Support/Code/User/settings.json etienne@192.168.2.38:/home/etienne/mac-backup/vscode/

brew deps --tree --installed > ~/homebrew-installed-packages.txt
rsync -ahP ~/homebrew-installed-packages.txt etienne@192.168.2.38:/home/etienne/mac-backup/

