#!/bin/bash

# Output script file name
output_script="install-vscode-extensions.sh"

# Generate the list of installed extensions
extensions=$(code --list-extensions)

# Check if `code` command works
if [ $? -ne 0 ]; then
  echo "Error: 'code' command not found. Make sure Visual Studio Code CLI is installed and accessible in PATH."
  exit 1
fi

# Write the installer script
echo "#!/bin/bash" > ~/scripts/$output_script
echo "" >> ~/scripts/$output_script
echo "# Script to install all currently installed VS Code extensions" >> ~/scripts/$output_script

# Add install commands for each extension
for extension in $extensions; do
  echo "code --install-extension $extension --force" >> ~/scripts/$output_script
done

# Make the output script executable
chmod +x ~/scripts/$output_script

echo "Installer script generated: $output_script"
echo "Run '~/scripts/$output_script' to install the extensions."
