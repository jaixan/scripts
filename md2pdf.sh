#!/bin/bash

# Check if pandoc is installed
if ! command -v pandoc &> /dev/null
then
 echo "Error: pandoc is not installed."
 echo "Please install it using 'brew install pandoc' or your preferred method."
 exit 1
fi

# Loop through all files in the current directory
for file in *; do
 # Check if the file ends with .md
 if [[ "$file" == *.md ]]; then
 # Extract the filename without the extension
 filename_without_ext="${file%.*}"
 # Construct the output PDF filename
 output_pdf="${filename_without_ext}.pdf"

 # Convert the Markdown file to PDF using pandoc
 echo "Converting '$file' to '$output_pdf'..."
 pandoc "$file" -o "$output_pdf"
 if [ $? -eq 0 ]; then
 echo "Successfully converted '$file' to '$output_pdf'."
 else
 echo "Error converting '$file' to '$output_pdf'."
 fi
 fi
done

echo "Conversion process finished."

    