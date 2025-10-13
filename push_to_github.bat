@echo off
echo ========================================
echo    Push VidNet to GitHub
echo ========================================
echo.

echo This script will help you push your VidNet code to GitHub
echo Make sure you have created a repository on GitHub first!
echo.

set /p repo_url="Enter your GitHub repository URL (e.g., https://github.com/username/vidnet.git): "

if "%repo_url%"=="" (
    echo ERROR: Repository URL is required
    pause
    exit /b 1
)

echo.
echo Adding GitHub remote...
git remote add origin %repo_url%

echo.
echo Setting main branch...
git branch -M main

echo.
echo Pushing to GitHub...
git push -u origin main

if errorlevel 1 (
    echo.
    echo ERROR: Failed to push to GitHub
    echo Make sure:
    echo 1. The repository exists on GitHub
    echo 2. You have write access to the repository
    echo 3. Your Git credentials are configured
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Successfully pushed to GitHub!
echo ========================================
echo.
echo Your VidNet code is now on GitHub at:
echo %repo_url%
echo.
echo Next steps:
echo 1. Go to https://render.com/dashboard
echo 2. Click "New +" then "Web Service"
echo 3. Connect your GitHub repository
echo 4. Render will auto-detect render.yaml
echo 5. Click "Create Web Service"
echo.
echo Your app will be deployed automatically!
echo.
pause