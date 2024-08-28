#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

# Start the bot based on the command-line argument
if [ "$1" = "tama" ]; then
    python main.py tama
elif [ "$1" = "saki" ]; then
    python main.py saki
else
    echo "Invalid bot specified."
fi
