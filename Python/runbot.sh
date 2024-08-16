#!/bin/bash

# Activate the virtual environment
source Discordbotenv/bin/activate

# Start the bot based on the command-line argument
if [ "$1" = "tama" ]; then
    python Bot.py tama
elif [ "$1" = "saki" ]; then
    python Bot.py saki
else
    echo "Invalid bot specified."
fi
