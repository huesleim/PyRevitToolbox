@echo off

py -m pip install -r requirements.txt

py -m PyInstaller --onedir --noconsole --name DWGMerger main_gui.py

echo.
echo Build finished: dist\DWGMerger\
echo.
echo NEXT STEP (do this manually once):
echo   1. Download ODA File Converter from https://www.opendesign.com/guestfiles/oda_file_converter
echo   2. Install it on THIS machine.
echo   3. Copy its install folder (normally C:\Program Files\ODA\ODAFileConverter)
echo      into dist\DWGMerger\, and rename the copied folder to exactly:
echo        ODAFileConverter
echo      so the final layout looks like:
echo        dist\DWGMerger\DWGMerger.exe
echo        dist\DWGMerger\ODAFileConverter\ODAFileConverter.exe
echo        dist\DWGMerger\ODAFileConverter\  (its other DLLs/support files)
echo.
echo Then zip dist\DWGMerger and hand the whole folder to colleagues.
echo They run DWGMerger.exe directly -- no installs needed on their machines.
pause
