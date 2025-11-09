@echo off
REM Quick deployment script for Heroku (Windows)

echo ============================================
echo Heroku Deployment Script for Windows
echo ============================================
echo.

REM Check if Heroku CLI is installed
where heroku >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo X Error: Heroku CLI is not installed
    echo Install it from: https://devcenter.heroku.com/articles/heroku-cli
    pause
    exit /b 1
)

echo [OK] Heroku CLI is installed
echo.

REM Check if logged in to Heroku
heroku auth:whoami >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Please login to Heroku:
    heroku login
)

echo [OK] Logged in to Heroku
echo.

REM Ask for app name
set /p APP_NAME="Enter your Heroku app name (or press Enter for auto-generated): "

REM Create Heroku app
if "%APP_NAME%"=="" (
    echo Creating Heroku app with auto-generated name...
    heroku create
) else (
    echo Creating Heroku app: %APP_NAME%...
    heroku create %APP_NAME%
)

echo.
echo [OK] Heroku app created
echo.

REM Add buildpacks
echo Adding buildpacks...
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-chromedriver
heroku buildpacks:add --index 3 heroku/python

echo.
echo [OK] Buildpacks added
echo.

REM Set environment variables
echo ============================================
echo Environment Configuration
echo ============================================
echo.

set /p OPENAI_KEY="Enter your OpenAI API key: "
set /p WEBFLOW_TOKEN="Enter your Webflow API token: "

heroku config:set OPENAI_API_KEY=%OPENAI_KEY%
heroku config:set WEBFLOW_TOKEN=%WEBFLOW_TOKEN%

echo.
echo [OK] Environment variables configured
echo.

REM Deploy
echo ============================================
echo Deploying to Heroku...
echo ============================================
echo.

git push heroku master
if %ERRORLEVEL% NEQ 0 (
    git push heroku main:master
)

echo.
echo [OK] Deployment complete
echo.

REM Scale dyno
heroku ps:scale web=1

echo.
echo [OK] Web dyno scaled
echo.

REM Get app info
echo ============================================
echo Deployment Successful!
echo ============================================
echo.
echo Your app is now live!
echo.
echo Test the health endpoint with:
echo   curl https://your-app-name.herokuapp.com/health
echo.
echo View logs with:
echo   heroku logs --tail
echo.
echo Open in browser with:
echo   heroku open
echo.

pause

