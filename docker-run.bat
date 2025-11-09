@echo off
REM Webflow CMS Automation - Docker Helper Script for Windows

echo ============================================
echo   Webflow CMS Automation - Docker Setup
echo ============================================
echo.

REM Check if .env file exists
if not exist .env (
    echo [WARNING] No .env file found
    echo.
    echo Creating .env file template...
    (
        echo # Required Environment Variables
        echo OPENAI_API_KEY=your_openai_api_key_here
        echo WEBFLOW_TOKEN=your_webflow_token_here
        echo.
        echo # Optional
        echo PORT=5000
    ) > .env
    echo [SUCCESS] Created .env file
    echo.
    echo [ERROR] Please edit .env file with your actual API keys before continuing!
    echo Then run this script again.
    pause
    exit /b 1
)

REM Load environment variables from .env
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if not "%%a"=="#" (
        if not "%%a"=="" (
            set %%a=%%b
        )
    )
)

REM Verify required environment variables
if "%OPENAI_API_KEY%"=="your_openai_api_key_here" (
    echo [ERROR] OPENAI_API_KEY not set in .env file
    pause
    exit /b 1
)

if "%WEBFLOW_TOKEN%"=="your_webflow_token_here" (
    echo [ERROR] WEBFLOW_TOKEN not set in .env file
    pause
    exit /b 1
)

echo [SUCCESS] Environment variables validated
echo.

REM Create necessary directories
echo Creating directories...
if not exist images mkdir images
if not exist best_match mkdir best_match
if not exist content mkdir content
echo [SUCCESS] Directories created
echo.

REM Build Docker image
echo Building Docker image...
docker build -t webflow-cms-automation .

if %errorlevel% neq 0 (
    echo [ERROR] Docker build failed
    pause
    exit /b 1
)

echo [SUCCESS] Docker image built successfully
echo.

REM Stop and remove existing container if running
docker ps -a -q -f name=webflow-cms-automation >nul 2>&1
if %errorlevel% equ 0 (
    echo Stopping existing container...
    docker stop webflow-cms-automation >nul 2>&1
    docker rm webflow-cms-automation >nul 2>&1
    echo [SUCCESS] Existing container removed
    echo.
)

REM Run container
echo Starting container...
docker run -d ^
    --name webflow-cms-automation ^
    -p 5000:5000 ^
    -e OPENAI_API_KEY=%OPENAI_API_KEY% ^
    -e WEBFLOW_TOKEN=%WEBFLOW_TOKEN% ^
    -e PORT=5000 ^
    -v "%cd%/content:/app/content" ^
    -v "%cd%/best_match:/app/best_match" ^
    --restart unless-stopped ^
    webflow-cms-automation

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start container
    pause
    exit /b 1
)

echo [SUCCESS] Container started successfully
echo.
echo ============================================
echo          Deployment Successful! 🚀
echo ============================================
echo.
echo Server is running at: http://localhost:5000
echo Health check: http://localhost:5000/health
echo.
echo Useful commands:
echo   View logs:    docker logs -f webflow-cms-automation
echo   Stop server:  docker stop webflow-cms-automation
echo   Start server: docker start webflow-cms-automation
echo   Restart:      docker restart webflow-cms-automation
echo   Remove:       docker rm -f webflow-cms-automation
echo.

REM Wait and check health
echo Checking health...
timeout /t 5 /nobreak >nul

curl -s http://localhost:5000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] Server is healthy and responding
) else (
    echo [WARNING] Server may still be starting up...
    echo Run: docker logs webflow-cms-automation
)

echo.
pause



