#!/bin/bash

# Progress bar function
progress_bar() {
    local current=$1
    local total=$2
    local text=$3
    local width=50  # Adjust the bar width here

    # Calculate progress percentage
    local percent=$((current * 100 / total))
    # Calculate the number of blocks to display
    local progress=$((current * width / total))

    # Create the bar strings
    printf -v bar "%${progress}s" ""          # Filled part
    printf -v remaining "%$((width - progress))s" ""  # Remaining part

    # Display the progress bar
    printf "\r[%-${width}s] %d%% %s" "${bar// /█}${remaining// / }" "$percent" "$text"
}

# Commands to execute (modify this array as needed)
commands=(
    'rsync -ahP --exclude=".DS_Store" ~/Documents root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP --exclude=".DS_Store" /Users/etiennerivard/Library/CloudStorage/OneDrive-CégepdeVictoriaville/CegepVicto root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP --exclude=".DS_Store" /Users/etiennerivard/Library/CloudStorage/OneDrive-CégepdeVictoriaville/Administration root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/notes_de_cours root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/projets root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/demo_cours root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP ~/.aliases root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP ~/.mrconfig root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP ~/.ssh root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    '~/scripts/generate-vscode-extensions-install.sh'
    'rsync -ahP --exclude=".DS_Store" --exclude='.git/' --exclude='node_modules/' --exclude='venv/' --exclude='sites/' --exclude='www/' ~/scripts root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP --exclude=".DS_Store" ~/Library/Application\ Support/Code/User/settings.json root@guizmo.profinfo.ca:/mnt/blockstorage/backup/vscode/'
    'brew deps --tree --installed > ~/homebrew-installed-packages.txt'
    'rsync -ahP ~/homebrew-installed-packages.txt root@guizmo.profinfo.ca:/mnt/blockstorage/backup/'
    'rsync -ahP root@guizmo.profinfo.ca:/mnt/blockstorage/coffre/bookmarks.xbel ~/notes_de_cours/bm/template/bookmarks.xbel'
    'cd ~/notes_de_cours/bm/ && ./xbel2md.py'
    'cd ~/notes_de_cours/bm/ && source venv/bin/activate && mkdocs gh-deploy'
)

# Text of commands to execute
command_texts=(
    '~/Documents                             '
    'OneDrive-CégepdeVictoriaville/CegepVicto'
    'OneDrive-CégepdeVictoriaville/Admin     '
    'notes_de_cours                          '
    'projets                                 '
    'demo_cours                              '
    '.aliases                                '
    '.mrconfig                               '
    '.ssh                                    '
    'generate-vscode-extensions-install.sh   '
    'scripts                                 '
    'vscode config                           '
    'brew deps --tree --installed            '
    'homebrew-installed-packages.txt         '
    'bookmarks.xbel                          '
    'generate markdown                       '
    'deploy bookmarks                        '
)

total_commands=${#commands[@]}
current_command=0

# Hide the cursor
printf "\033[?25l"
printf "Backup in progress...\n"
progress_bar "0" "$total_commands" "Starting"

# Execute each command
for cmd in "${commands[@]}"; do
    # Run the command, redirecting output to avoid clutter
    eval "$cmd" > /dev/null 2>&1

    # Check for command failure
    if [ $? -ne 0 ]; then
        printf "\nError: Command failed — %s\n" "$cmd"
        printf "\033[?25h"  # Restore cursor
        exit 1
    fi

    # Update progress
    ((current_command++))
    progress_bar "$current_command" "$total_commands" "${command_texts[$current_command - 1]}"
done

# Ensure the progress bar ends at 100%
progress_bar "$total_commands" "$total_commands"

# Restore the cursor and move to a new line
printf "\033[?25h\n"
