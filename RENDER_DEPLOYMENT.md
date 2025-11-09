# Deploy to Render.com (100% Free, No Credit Card)

[Render.com](https://render.com) is a modern cloud platform with a **truly free tier** that **doesn't require a credit card**.

## ✨ Why Render?

- ✅ **Completely FREE** - No credit card required
- ✅ **Always on** - Spins down after 15 minutes of inactivity but restarts automatically
- ✅ **750 hours/month** free
- ✅ **Docker support** - Works with your existing Dockerfile
- ✅ **Auto SSL/HTTPS** - Free SSL certificates
- ✅ **Easy deployment** - Simple git-based workflow

## 🚀 Quick Deploy (5 Minutes)

### Method 1: One-Click Deploy from GitHub (Easiest)

1. **Push your code to GitHub** (if not already):
   ```bash
   git add .
   git commit -m "Add Render deployment config"
   git push origin master
   ```

2. **Go to Render Dashboard**:
   - Visit: https://dashboard.render.com/
   - Sign up with GitHub (free, no credit card)

3. **Create New Web Service**:
   - Click **"New +"** → **"Web Service"**
   - Connect your GitHub repository
   - Render will detect your `render.yaml` automatically

4. **Configure Environment Variables**:
   - Add `OPENAI_API_KEY` = your OpenAI key
   - Add `WEBFLOW_TOKEN` = your Webflow token
   - `PORT` is auto-set to 10000

5. **Deploy**:
   - Click **"Create Web Service"**
   - Render will build and deploy automatically
   - Wait 5-10 minutes for first deployment

### Method 2: Manual Setup (More Control)

1. **Sign up at Render**: https://dashboard.render.com/register

2. **Create New Web Service**:
   - Click **"New +"** → **"Web Service"**
   - Connect your GitHub repo
   - Or use: **"Deploy an existing image from a registry"**

3. **Configure Service**:
   ```
   Name: webflow-cms-automation
   Environment: Docker
   Region: Oregon (or closest to you)
   Branch: master
   Plan: Free
   ```

4. **Build Settings**:
   ```
   Docker Command: (leave empty, uses Dockerfile CMD)
   ```

5. **Environment Variables**:
   ```
   OPENAI_API_KEY = sk-your-key-here
   WEBFLOW_TOKEN = your-token-here
   ```

6. **Advanced Settings** (Optional):
   ```
   Health Check Path: /health
   ```

7. **Click "Create Web Service"**

## 🧪 Testing Your Deployment

Once deployed, your app will be at: `https://your-app-name.onrender.com`

```bash
# Test health endpoint
curl https://your-app-name.onrender.com/health

# Test webhook
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

## 📊 Free Tier Limitations

| Feature | Free Tier |
|---------|-----------|
| **Cost** | $0/month (no credit card!) |
| **Hours** | 750 hours/month |
| **Memory** | 512 MB RAM |
| **Builds** | 400 build hours/month |
| **Bandwidth** | 100 GB/month |
| **Sleeping** | No automatic sleep |
| **SSL** | Free HTTPS |

**Important:** Free tier has:
- Slower builds (can take 5-10 minutes)
- Less CPU priority
- Services may be spun down after 15 minutes of inactivity (but start automatically on request)

## 🔄 Auto-Deploy from GitHub

Enable automatic deployments:

1. Go to your service in Render Dashboard
2. Navigate to **"Settings"** → **"Build & Deploy"**
3. Enable **"Auto-Deploy"** for your branch
4. Every push to GitHub will automatically deploy

## 📝 Managing Your App

### View Logs
In Render Dashboard:
- Go to your service
- Click **"Logs"** tab
- Real-time logs appear automatically

### Environment Variables
- Go to **"Environment"** tab
- Add/edit variables
- Changes trigger automatic redeployment

### Manual Deploy
- Go to **"Manual Deploy"** tab
- Click **"Deploy latest commit"**

### Restart Service
- Go to **"Settings"**
- Click **"Manual Deploy"** → **"Clear build cache & deploy"**

## 💡 Tips for Free Tier

1. **First build is slow** - Render compiles everything from scratch (5-10 min)
2. **Subsequent builds are faster** - Uses caching (~2-3 min)
3. **Service spins down** - After 15 min inactivity, restarts on first request (adds ~30s delay)
4. **Keep it warm** - Use a service like UptimeRobot to ping your health endpoint every 10 minutes

### Keep Service Warm (Optional)

Use [UptimeRobot](https://uptimerobot.com/) (also free):
1. Sign up at UptimeRobot
2. Add monitor: `https://your-app.onrender.com/health`
3. Set interval: 5 minutes
4. This keeps your service active

## 🔧 Troubleshooting

### Build Fails?

Check these:
- `Dockerfile` exists and is valid
- `requirements.txt` has all dependencies
- Environment variables are set correctly

### Chrome/Selenium Errors?

Your `Dockerfile` already includes Chrome setup. If issues occur:
- Check Render logs for specific errors
- Verify Chrome is installing correctly in build logs

### Timeout Errors?

Render free tier has 30-second request timeout. Your app has long-running operations:
- Each webhook request can take several minutes
- Consider breaking into smaller batches (reduce `count`)
- Or upgrade to paid tier ($7/month) for longer timeouts

### Out of Memory?

Free tier has 512 MB RAM:
- Reduce concurrent operations
- Process fewer images at once
- Upgrade to Starter plan ($7/month) for 512 MB → 2 GB

## 💰 Upgrade Options (If Needed)

If free tier isn't enough:

| Plan | Cost | RAM | Timeout |
|------|------|-----|---------|
| **Free** | $0 | 512 MB | 30s |
| **Starter** | $7/month | 512 MB | 300s |
| **Standard** | $25/month | 2 GB | 300s |

```bash
# Upgrade in Render Dashboard:
# Settings → Plan → Select plan → Upgrade
```

## 🔐 Security Best Practices

1. **Never commit API keys** - Use environment variables only
2. **Use environment tab** - Set secrets in Render Dashboard
3. **Enable 2FA** - On your Render account
4. **Monitor logs** - Check for suspicious activity
5. **Add webhook auth** - Consider adding API key validation to your `/webhook` endpoint

## 🌐 Custom Domain (Free)

Render allows custom domains even on free tier:

1. Go to **"Settings"** → **"Custom Domain"**
2. Add your domain
3. Update DNS records as instructed
4. Free SSL certificate auto-generated

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [Render Status Page](https://status.render.com/)
- [Render Community](https://community.render.com/)

## 🎉 You're All Set!

Your Webflow CMS Automation is now running on Render for **100% FREE** with **no credit card required**! 🚀

## Common Commands Reference

**View Logs:**
- Render Dashboard → Your Service → Logs tab

**Restart Service:**
- Render Dashboard → Manual Deploy → Deploy latest commit

**Update Environment Variables:**
- Render Dashboard → Environment tab → Add variable

**Monitor Status:**
- Render Dashboard → Metrics tab

---

**Need help?** Check the [Render documentation](https://render.com/docs) or our main [README.md](README.md)

