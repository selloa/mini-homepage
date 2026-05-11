@echo off
REM Generate MMM forum BBCode from mmm_episoden_links.csv

setlocal
cd /d "%~dp0"

python scripts\mmm_episoden_csv_to_forumcode.py -o mmm_episoden_forumcode.txt
set ERR=%ERRORLEVEL%

if %ERR% NEQ 0 (
    echo.
    echo Fehler beim Generieren ^(Exit-Code %ERR%^).
    pause
    exit /b %ERR%
)

echo.
echo Erfolgreich erzeugt: mmm_episoden_forumcode.txt
pause
endlocal
