@echo off

REM Activate the virtual environment
call Discordbotenv\Scripts\activate

REM Start TamaBot in a new command prompt window
start cmd /k python Bot.py tama