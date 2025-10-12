@echo off
echo ========================================
echo    Preparing VidNet for Deployment
echo ========================================
echo.

echo Checking Git status...
git status

echo.
echo Adding all files...
git add .

echo.
echo Committing changes...
git commit -m "Ready for VidNet deployment"

echo.
echo Pushing to GitHub...
git push origin main

echo.
echo ========================================
echo   Ready for Render Deployment!
echo ========================================
echo.
echo Next steps:
echo 1. Go to https://render.com/dashboard
echo 2. Create new Web Service from your GitHub repo
echo 3. Render will auto-detect render.yaml
echo.
pause
