@echo off
echo ==================================================
echo         Welcome to MovieRec Auto-Updater
echo ==================================================
echo.
echo [1/2] Fetching the latest Top 10,000 movies from TMDB...
python smart_tmdb_fetcher.py

echo.
echo [2/2] Scanning for new movies and updating FAISS AI Index...
python update_index.py

echo.
echo ==================================================
echo         Update Complete! 
echo ==================================================
echo.
echo The AI index has been successfully refreshed with live data.
echo If your Flask server (app.py) is currently running, you must 
echo restart it to load the new FAISS index into memory.
echo.
pause
