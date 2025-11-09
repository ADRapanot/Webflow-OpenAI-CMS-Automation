#!/bin/bash
# Quick deployment script for Heroku

set -e

echo "============================================"
echo "Heroku Deployment Script"
echo "============================================"
echo ""

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Error: Heroku CLI is not installed"
    echo "Install it from: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

echo "✓ Heroku CLI is installed"
echo ""

# Check if logged in to Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "Please login to Heroku:"
    heroku login
fi

echo "✓ Logged in to Heroku"
echo ""

# Ask for app name
read -p "Enter your Heroku app name (or press Enter for auto-generated): " APP_NAME

# Create Heroku app
if [ -z "$APP_NAME" ]; then
    echo "Creating Heroku app with auto-generated name..."
    heroku create
else
    echo "Creating Heroku app: $APP_NAME..."
    heroku create "$APP_NAME"
fi

echo ""
echo "✓ Heroku app created"
echo ""

# Add buildpacks
echo "Adding buildpacks..."
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-chromedriver
heroku buildpacks:add --index 3 heroku/python

echo ""
echo "✓ Buildpacks added"
echo ""

# Set environment variables
echo "============================================"
echo "Environment Configuration"
echo "============================================"
echo ""

read -p "Enter your OpenAI API key: " OPENAI_KEY
read -p "Enter your Webflow API token: " WEBFLOW_TOKEN

heroku config:set OPENAI_API_KEY="$OPENAI_KEY"
heroku config:set WEBFLOW_TOKEN="$WEBFLOW_TOKEN"

echo ""
echo "✓ Environment variables configured"
echo ""

# Deploy
echo "============================================"
echo "Deploying to Heroku..."
echo "============================================"
echo ""

git push heroku master || git push heroku main:master

echo ""
echo "✓ Deployment complete"
echo ""

# Scale dyno
heroku ps:scale web=1

echo ""
echo "✓ Web dyno scaled"
echo ""

# Get app URL
APP_URL=$(heroku info -s | grep web_url | cut -d= -f2)

echo "============================================"
echo "Deployment Successful! 🎉"
echo "============================================"
echo ""
echo "Your app is live at: $APP_URL"
echo ""
echo "Test the health endpoint:"
echo "  curl ${APP_URL}health"
echo ""
echo "View logs:"
echo "  heroku logs --tail"
echo ""
echo "Open in browser:"
echo "  heroku open"
echo ""

