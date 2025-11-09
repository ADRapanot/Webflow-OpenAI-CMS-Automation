# Heroku Quick Start Guide

Get your Webflow CMS Automation service running on Heroku in under 10 minutes!

## Prerequisites

- Heroku account (free tier works)
- OpenAI API key
- Webflow API token
- Git installed

## Option 1: One-Click Deploy (Easiest)

Click this button:

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

You'll be prompted to enter:

- `OPENAI_API_KEY` - Your OpenAI API key
- `WEBFLOW_TOKEN` - Your Webflow API token

That's it! Your app will be deployed automatically.

## Option 2: Automated Script Deploy

### Windows:

```bash
deploy-heroku.bat
```

### Mac/Linux:

```bash
./deploy-heroku.sh
```

Follow the prompts to enter your API keys.

## Option 3: Manual Deploy (Full Control)

```bash
# 1. Install Heroku CLI
# Download from: https://devcenter.heroku.com/articles/heroku-cli

# 2. Login
heroku login

# 3. Create app
heroku create your-app-name

# 4. Add buildpacks (Chrome for Selenium)
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-chromedriver
heroku buildpacks:add --index 3 heroku/python

# 5. Set environment variables
heroku config:set OPENAI_API_KEY=sk-your-key-here
heroku config:set WEBFLOW_TOKEN=your-token-here

# 6. Deploy
git push heroku master
# Or if on main branch:
# git push heroku main:master

# 7. Scale web dyno
heroku ps:scale web=1
```

## Testing Your Deployment

```bash
# Check health endpoint
curl https://your-app-name.herokuapp.com/health

# Expected: {"status": "ok"}
```

## Test the Webhook

```bash
curl -X POST https://your-app-name.herokuapp.com/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "collection_id": "YOUR_COLLECTION_ID",
    "site_id": "YOUR_SITE_ID",
    "fieldData": {
      "slug": "marketing-analytics",
      "category": "Marketing"
    },
    "count": 3
  }'
```

## Common Commands

```bash
# View logs
heroku logs --tail

# Check dyno status
heroku ps

# Open app in browser
heroku open

# View environment variables
heroku config

# Restart app
heroku restart

# Scale to 0 (stop app, save dyno hours)
heroku ps:scale web=0

# Scale back up
heroku ps:scale web=1
```

## Costs

### Free Tier

- 550-1000 free dyno hours/month
- App sleeps after 30 minutes of inactivity
- Perfect for testing and low-traffic usage

### Paid Tiers

- **Basic Dyno**: $7/month
  - Never sleeps
  - Better for production
- **Standard-1X**: $25/month
  - More resources
  - Better performance for image processing

```bash
# Upgrade to Basic
heroku ps:resize web=basic

# Upgrade to Standard-1X
heroku ps:resize web=standard-1x
```

## Troubleshooting

### App crashes on startup?

```bash
heroku logs --tail
# Check for missing environment variables or errors
```

### Timeout errors (H12)?

- The `Procfile` is configured with 5-minute timeout
- For longer operations, consider upgrading to Standard dyno

### Chrome/Selenium errors?

```bash
# Verify buildpacks
heroku buildpacks

# Should show:
# 1. heroku-buildpack-google-chrome
# 2. heroku-buildpack-chromedriver
# 3. heroku/python
```

### Out of memory (R14/R15 errors)?

```bash
# Upgrade to larger dyno
heroku ps:resize web=standard-2x
```

## Next Steps

1. **Set up monitoring**: Use Heroku Dashboard to track app performance
2. **Configure custom domain** (paid plans only)
3. **Enable automatic deploys** from GitHub
4. **Set up staging environment** using Heroku Pipelines

## Getting Help

- 📖 Full Documentation: [HEROKU_DEPLOYMENT.md](HEROKU_DEPLOYMENT.md)
- 🏠 Project README: [README.md](README.md)
- 💬 Heroku Support: https://help.heroku.com/

## Environment Variables Reference

| Variable         | Required | Description                             |
| ---------------- | -------- | --------------------------------------- |
| `OPENAI_API_KEY` | ✅ Yes   | OpenAI API key for GPT and vision       |
| `WEBFLOW_TOKEN`  | ✅ Yes   | Webflow API token with CMS write access |
| `PORT`           | ⚪ No    | Auto-set by Heroku                      |

That's it! Your Webflow CMS Automation service is now live! 🚀
