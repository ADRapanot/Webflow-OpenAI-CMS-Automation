# Deploying to Heroku

This guide will help you deploy the Webflow CMS Automation service to Heroku.

## Prerequisites

1. **Heroku Account** - Sign up at [heroku.com](https://heroku.com)
2. **Heroku CLI** - Install from [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)
3. **Git** - Ensure your project is in a Git repository
4. **API Keys**:
   - OpenAI API key
   - Webflow API token with CMS write permissions

## Quick Deploy (One-Click)

Click the button below to deploy directly to Heroku:

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

You'll be prompted to enter your API keys during setup.

## Manual Deployment

### Step 1: Install Heroku CLI

If you haven't already, install the Heroku CLI:

**Windows:**

```bash
# Download and run installer from:
# https://devcenter.heroku.com/articles/heroku-cli
```

**macOS:**

```bash
brew tap heroku/brew && brew install heroku
```

**Linux:**

```bash
curl https://cli-assets.heroku.com/install.sh | sh
```

### Step 2: Login to Heroku

```bash
heroku login
```

This will open a browser window for authentication.

### Step 3: Create a Heroku App

```bash
heroku create your-app-name
# Or let Heroku generate a random name:
# heroku create
```

This command will:

- Create a new Heroku app
- Add a git remote named `heroku` to your repository

### Step 4: Add Required Buildpacks

Since this app uses Selenium with Chrome, we need special buildpacks:

```bash
# Add Google Chrome buildpack
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-google-chrome

# Add ChromeDriver buildpack
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-chromedriver

# Add Python buildpack
heroku buildpacks:add --index 3 heroku/python
```

Verify buildpacks are added correctly:

```bash
heroku buildpacks
```

Expected output:

```
=== your-app-name Buildpack URLs
1. https://github.com/heroku/heroku-buildpack-google-chrome
2. https://github.com/heroku/heroku-buildpack-chromedriver
3. heroku/python
```

### Step 5: Configure Environment Variables

Set your API keys and configuration:

```bash
# Required API keys
heroku config:set OPENAI_API_KEY=sk-your-openai-key-here
heroku config:set WEBFLOW_TOKEN=your-webflow-token-here

# Optional: Port is set automatically by Heroku
# heroku config:set PORT=5000
```

Verify configuration:

```bash
heroku config
```

### Step 6: Configure Chrome for Heroku

Update `scrape_images_js.py` to ensure it works on Heroku. The Chrome options should already be set correctly, but verify the following options are present:

```python
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--headless')
```

These are critical for Chrome to run in Heroku's containerized environment.

### Step 7: Commit Your Changes

If you've made any changes, commit them:

```bash
git add .
git commit -m "Prepare for Heroku deployment"
```

### Step 8: Deploy to Heroku

```bash
git push heroku master
# Or if you're on a different branch:
# git push heroku your-branch:master
```

Heroku will:

1. Receive your code
2. Install Python and dependencies from `requirements.txt`
3. Install Chrome and ChromeDriver
4. Start your Flask application

### Step 9: Scale the Web Dyno

Ensure at least one web dyno is running:

```bash
heroku ps:scale web=1
```

### Step 10: Verify Deployment

Check your app status:

```bash
heroku ps
```

View logs:

```bash
heroku logs --tail
```

Test the health endpoint:

```bash
curl https://your-app-name.herokuapp.com/health
```

Expected response:

```json
{ "status": "ok" }
```

## Testing the Webhook Endpoint

Once deployed, test your webhook:

```bash
curl -X POST https://your-app-name.herokuapp.com/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "collection_id": "your-collection-id",
    "site_id": "your-site-id",
    "fieldData": {
      "slug": "marketing-analytics",
      "category": "Marketing"
    },
    "count": 3
  }'
```

## Configuration Files

The following files are used for Heroku deployment:

- **`Procfile`** - Defines how Heroku runs your app
- **`runtime.txt`** - Specifies Python version
- **`requirements.txt`** - Python dependencies
- **`app.json`** - Configuration for Heroku deployment button

## Monitoring and Logs

### View Real-Time Logs

```bash
heroku logs --tail
```

### View Recent Logs

```bash
heroku logs -n 500
```

### Open App in Browser

```bash
heroku open
```

### Check Dyno Status

```bash
heroku ps
```

## Troubleshooting

### Chrome/ChromeDriver Issues

If you see errors related to Chrome or ChromeDriver:

1. Verify buildpacks are installed in correct order:

   ```bash
   heroku buildpacks
   ```

2. Check Chrome is installed:

   ```bash
   heroku run "which google-chrome-stable"
   ```

3. Check ChromeDriver is installed:
   ```bash
   heroku run "which chromedriver"
   ```

### Memory Issues

If your app crashes due to memory (R14/R15 errors), consider:

1. Upgrade to a larger dyno:

   ```bash
   heroku ps:resize web=standard-2x
   ```

2. Reduce concurrent processing in your code

### Timeout Issues

If webhook requests timeout (H12 errors):

1. The `Procfile` already sets `--timeout 300` (5 minutes)
2. For longer operations, consider background workers with Celery
3. Or use Heroku's extended timeout on Professional dynos

### Environment Variables Not Set

List all config vars:

```bash
heroku config
```

Set missing variables:

```bash
heroku config:set VARIABLE_NAME=value
```

### Build Failures

If deployment fails during build:

1. Check Python version in `runtime.txt` matches Heroku's supported versions:

   ```bash
   heroku buildpacks:info heroku/python
   ```

2. Verify all dependencies in `requirements.txt` are valid

3. Check build logs:
   ```bash
   heroku logs --tail
   ```

## Upgrading Python Version

To upgrade Python:

1. Update `runtime.txt` with new version:

   ```
   python-3.11.9
   ```

2. Commit and push:
   ```bash
   git add runtime.txt
   git commit -m "Upgrade Python version"
   git push heroku master
   ```

## Managing Costs

### Free Tier Limitations

- Free dynos sleep after 30 minutes of inactivity
- 550-1000 free dyno hours per month
- No custom domains on free tier

### Upgrading

```bash
# Upgrade to Basic dyno ($7/month)
heroku ps:resize web=basic

# Upgrade to Standard-1X dyno ($25/month)
heroku ps:resize web=standard-1x
```

## Database (Optional)

If you need persistent storage:

```bash
# Add PostgreSQL
heroku addons:create heroku-postgresql:mini

# Add Redis (for caching/queuing)
heroku addons:create heroku-redis:mini
```

## Custom Domain (Paid Plans)

```bash
heroku domains:add www.yourdomain.com
heroku domains:add yourdomain.com
```

Then configure your DNS provider with the provided DNS targets.

## SSL/HTTPS

All Heroku apps automatically get free SSL certificates via Let's Encrypt.

Your app will be accessible via:

- `https://your-app-name.herokuapp.com`

## Continuous Deployment

### GitHub Integration

1. Go to Heroku Dashboard
2. Navigate to your app
3. Click "Deploy" tab
4. Connect to GitHub
5. Enable "Automatic Deploys" from your main branch

Now every push to your GitHub repository will automatically deploy to Heroku.

### Using Heroku Pipelines

For staging and production environments:

```bash
# Create pipeline
heroku pipelines:create your-pipeline-name

# Add apps to pipeline
heroku pipelines:add your-pipeline-name --app your-staging-app --stage staging
heroku pipelines:add your-pipeline-name --app your-production-app --stage production

# Promote staging to production
heroku pipelines:promote --app your-staging-app
```

## Backing Up

### Backup Configuration

```bash
# Export all config vars
heroku config --shell > .env.heroku.backup
```

### Rollback Deployment

```bash
# View releases
heroku releases

# Rollback to previous release
heroku rollback
```

## Scaling

### Scale Web Dynos

```bash
# Scale up
heroku ps:scale web=2

# Scale down
heroku ps:scale web=1
```

### Add Worker Dynos (for background jobs)

If you add Celery or similar:

```bash
heroku ps:scale worker=1
```

## Production Best Practices

1. **Use Environment Variables** - Never commit API keys
2. **Enable Auto-SSL** - Heroku provides this by default
3. **Set up Monitoring** - Use Heroku Dashboard or integrate with services like New Relic
4. **Regular Backups** - Export config and data regularly
5. **Health Checks** - Heroku automatically checks your app's health
6. **Implement Rate Limiting** - Protect your webhook endpoint
7. **Add Authentication** - Secure the `/webhook` endpoint in production

## Additional Resources

- [Heroku Python Documentation](https://devcenter.heroku.com/categories/python-support)
- [Heroku Chrome Buildpack](https://github.com/heroku/heroku-buildpack-google-chrome)
- [Heroku Deployment Guide](https://devcenter.heroku.com/articles/deploying-python)
- [Heroku CLI Commands](https://devcenter.heroku.com/articles/heroku-cli-commands)

## Support

For issues specific to this application, refer to the main README.md.

For Heroku-specific issues, consult [Heroku Dev Center](https://devcenter.heroku.com/).
