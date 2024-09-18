#!/bin/bash

# Create the virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install wheel and dependencies
pip install wheel
pip install -r piplist.txt

# Create directories
mkdir -p Media/Music/

# Deactivate the virtual environment
deactivate

echo "Bot Installed, Please use runbot.sh for Linux"
