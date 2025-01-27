#!/bin/zsh

rsync -ahP --exclude=".DS_Store" ~/Documents root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP --exclude=".DS_Store" /Users/etiennerivard/Library/CloudStorage/Dropbox root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP --exclude=".DS_Store" /Users/etiennerivard/Library/CloudStorage/OneDrive-CégepdeVictoriaville/CegepVicto root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/notes_de_cours root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/projets root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/demo_cours root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP ~/.aliases root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP ~/.mrconfig root@guizmo.profinfo.ca:/mnt/blockstorage/backup/
rsync -ahP ~/.ssh root@guizmo.profinfo.ca:/mnt/blockstorage/backup/

~/scripts/generate-vscode-extensions-install.sh
rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/scripts root@guizmo.profinfo.ca:/mnt/blockstorage/backup/

rsync -ahP --exclude=".DS_Store" ~/Library/Application\ Support/Code/User/settings.json root@guizmo.profinfo.ca:/mnt/blockstorage/backup/vscode/

brew deps --tree --installed > ~/homebrew-installed-packages.txt
rsync -ahP ~/homebrew-installed-packages.txt root@guizmo.profinfo.ca:/mnt/blockstorage/backup/

