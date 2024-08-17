#!/bin/bash

sudo chown -R xanmal:xanmal /home/xanmal/xanfiles/servers/DiscordBot

chmod -R +x /home/xanmal/xanfiles/servers/DiscordBot

python3 -m venv Discordbotenv

source Discordbotenv/bin/activate

pip install -r piplist.txt

touch config.py

mkdir -p Media/Music/

deactivate

echo "Bot Installed, Please use runbot.sh for linux"