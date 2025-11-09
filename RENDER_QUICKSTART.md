# Render.com Quick Start (5 Minutes, 100% Free)

Deploy your Webflow CMS Automation in 5 minutes with **zero cost** and **no credit card required**.

## ✨ What is Render?

Render is like Heroku but with a **truly free tier** that doesn't require a credit card. Perfect for this project!

## 🚀 Deploy in 5 Steps

### Step 1: Push to GitHub (if not already)

```bash
git add .
git commit -m "Ready for Render deployment"
git push origin master
```

### Step 2: Sign Up at Render

- Go to: **https://dashboard.render.com/register**
- Click **"Sign Up with GitHub"** (easiest)
- Authorize Render to access your repositories

### Step 3: Create New Web Service

1. In Render Dashboard, click **"New +"** (top right)
2. Select **"Web Service"**
3. Find and click your `Webflow-CMS-Automation` repository
4. Click **"Connect"**

### Step 4: Configure Your Service

Render will show a configuration form. Fill in:

| Field       | Value                                     |
| ----------- | ----------------------------------------- |
| **Name**    | `webflow-cms-automation` (or your choice) |
| **Region**  | Oregon (or closest to you)                |
| **Branch**  | `master` (or `main`)                      |
| **Runtime** | Docker                                    |
| **Plan**    | **Free** ⭐                               |

### Step 5: Add Environment Variables

Scroll down to **"Environment Variables"** section:

Click **"Add Environment Variable"** twice and add:

1. **Key:** `OPENAI_API_KEY` **Value:** `sk-your-openai-key-here`
2. **Key:** `WEBFLOW_TOKEN` **Value:** `your-webflow-token-here`

Then click **"Create Web Service"** at the bottom!

## ⏱️ Wait for Deployment

- First deployment takes **5-10 minutes** (it's building Chrome, Python, etc.)
- Watch the build logs in real-time
- When you see "Your service is live 🎉" - you're done!

## 🧪 Test Your Deployment

Your app will be at: `https://your-app-name.onrender.com`

### Test Health Endpoint

```bash
curl https://your-app-name.onrender.com/health
```

Expected response:

```json
{ "status": "ok" }
```

### Test Webhook

```bash
curl -X POST https://your-app-name.onrender.com/webhook \
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

## ✅ You're Done!

Your Webflow CMS Automation is now live and running **100% FREE** with **no credit card** required! 🎉

## 📊 What You Get (Free Tier)

- ✅ **750 hours/month** of runtime (more than enough)
- ✅ **Free SSL/HTTPS** automatically
- ✅ **512 MB RAM**
- ✅ **No credit card required**
- ✅ **100 GB bandwidth/month**
- ✅ **Auto-deploys** from GitHub (optional)

## 📝 Common Tasks

### View Logs

In Render Dashboard:

- Go to your service
- Click **"Logs"** tab (left sidebar)
- See real-time logs

### Update Environment Variables

- Go to your service
- Click **"Environment"** tab
- Edit or add variables
- Changes auto-deploy

### Manual Redeploy

- Go to **"Manual Deploy"** tab
- Click **"Deploy latest commit"**

### Enable Auto-Deploy from GitHub

- Go to **"Settings"** tab
- Under **"Build & Deploy"**
- Enable **"Auto-Deploy"** for your branch
- Every push to GitHub = automatic deployment

## ⚡ Keep Service Active (Optional)

Free tier services spin down after 15 minutes of inactivity (but auto-restart on requests).

To keep your service always warm, use **UptimeRobot** (also free):

1. Sign up at: https://uptimerobot.com/
2. Add New Monitor:
   - **Monitor Type:** HTTP(s)
   - **URL:** `https://your-app-name.onrender.com/health`
   - **Monitoring Interval:** 5 minutes
3. Done! Your service stays warm

## 🆘 Troubleshooting

### Build Failing?

Check these:

- ✅ `Dockerfile` exists in your repo
- ✅ `requirements.txt` exists
- ✅ Code is pushed to GitHub
- ✅ Branch name is correct

### Service Not Starting?

- Check **Logs** tab for errors
- Verify environment variables are set correctly
- Make sure both `OPENAI_API_KEY` and `WEBFLOW_TOKEN` are added

### Timeout Errors?

Free tier has **30-second timeout**. If webhook requests timeout:

- Reduce `count` parameter (try `count: 2` instead of `count: 5`)
- Process fewer items per request
- Consider upgrading to Starter plan ($7/month) for 5-minute timeout

### Chrome/Selenium Errors?

Your Dockerfile already handles Chrome setup. If issues occur:

- Check build logs to see if Chrome installed correctly
- Verify Docker build completed successfully
- Try redeploying: **Manual Deploy** → **"Clear build cache & deploy"**

## 💰 Upgrade Options (Optional)

If free tier isn't enough:

| Plan         | Cost   | RAM    | Timeout | Use Case             |
| ------------ | ------ | ------ | ------- | -------------------- |
| **Free**     | $0     | 512 MB | 30s     | Testing, low traffic |
| **Starter**  | $7/mo  | 512 MB | 300s    | Production           |
| **Standard** | $25/mo | 2 GB   | 300s    | High traffic         |

To upgrade:

- Go to **"Settings"** tab
- Click **"Change Plan"**
- Select your plan

## 🎯 Next Steps

1. ✅ **Test your deployment** - Try the health and webhook endpoints
2. ✅ **Set up UptimeRobot** - Keep service warm
3. ✅ **Enable Auto-Deploy** - Deploy automatically from GitHub
4. ✅ **Add custom domain** (optional, still free!)
5. ✅ **Monitor logs** - Watch your first few requests

## 📚 More Documentation

- **Full Render Guide:** [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)
- **All Free Options:** [FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md)
- **Project README:** [README.md](README.md)

## 🎉 Success!

You now have a production-ready Webflow CMS Automation service running in the cloud for **FREE**!

Your app URL: `https://your-app-name.onrender.com`

Start sending webhook requests and watch the magic happen! ✨

---

**Questions?** Check the [full Render deployment guide](RENDER_DEPLOYMENT.md) or [all free hosting options](FREE_HOSTING_OPTIONS.md).
