@echo off

REM Activate the virtual environment
call Discordbotenv\Scripts\activate

REM Start TamaBot in a new command prompt window
start cmd /k python Bot.py tama

REM Wait for a moment before starting SakiBot
timeout /t 5 /nobreak >nul

REM Start SakiBot in a new command prompt window
start cmd /k python Bot.py saki
