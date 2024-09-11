import os
import platform

def is_windows():
    return platform.system() == 'Windows'

def create_update_script():
    if is_windows():
        script_content = """@echo off

REM Create the virtual environment
python -m venv venv

REM Activate the virtual environment
call venv\\Scripts\\activate

REM Install wheel and dependencies
pip install wheel
pip install -r piplist.txt

REM Create directories
mkdir Media\\Music\\

REM Deactivate the virtual environment
deactivate

echo "Bot Installed, Please use runbot.bat for Windows"
pause
"""
        with open("updatebot.bat", "w") as bat_file:
            bat_file.write(script_content)
    else:
        script_content = """#!/bin/bash

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
"""
        with open("updatebot.sh", "w") as sh_file:
            sh_file.write(script_content)
        # Make the script executable
        os.chmod("updatebot.sh", 0o755)

def create_run_script():
    if is_windows():
        script_content = """@echo off

REM Activate the virtual environment
call venv\\Scripts\\activate

REM Start TamaBot in a new command prompt window
start cmd /k python main.py tama

REM Wait for a moment before starting SakiBot
timeout /t 5 /nobreak >nul

REM Start SakiBot in a new command prompt window
start cmd /k python main.py saki
"""
        with open("runbot.bat", "w") as bat_file:
            bat_file.write(script_content)
    else:
        script_content = """#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

# Start TamaBot
python main.py tama &

# Wait for a moment before starting SakiBot
sleep 5

# Start SakiBot
python main.py saki
"""
        with open("runbot.sh", "w") as sh_file:
            sh_file.write(script_content)
        # Make the script executable
        os.chmod("runbot.sh", 0o755)


def main():
    
    # Create necessary scripts
    create_update_script()
    create_run_script() 

    print("Setup complete.")
    if is_windows():
        print("The 'updatebot.bat' and 'runbot.bat' files have been created.")
        print("Run 'updatebot.bat' to set up the environment.")
        print("Then run 'runbot.bat' to start the bots.")
    else:
        print("The 'updatebot.sh' and 'runbot.sh' files have been created.")
        print("Run './updatebot.sh' to set up the environment.")
        print("Then run './runbot.sh' to start the bots.")

if __name__ == "__main__":
    main()
