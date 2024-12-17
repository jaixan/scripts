#!/bin/bash

# Check if a parameter was provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <parameter>"
    exit 1
fi

# Call the Python script with the provided parameter
sudo python3.13 ~/scripts/check_final.py "$1"
sudo chmod -R 777 ./extracted_apache2
