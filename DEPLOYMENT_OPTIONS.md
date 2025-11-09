# 🚀 Deployment Options Overview

Your project supports multiple deployment methods. Choose the one that best fits your needs!

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT OPTIONS                           │
└─────────────────────────────────────────────────────────────────┘

         ┌──────────────┐              ┌──────────────┐
         │    DOCKER    │              │   MANUAL     │
         │  (Container) │              │   (Server)   │
         └──────────────┘              └──────────────┘
               │                             │
               ▼                             ▼
         Cross-Platform                Full Control
         Reproducible                  Any Server
         Local or Cloud                Custom Setup
```

## 🐳 Option 1: Docker

**Best for:** Local development, reproducible environments, any cloud provider

### Deploy with Docker:

```bash
# Using docker-compose (easiest)
docker-compose up -d

# Or using plain Docker
docker build -t webflow-cms-automation .
docker run -d -p 5000:5000 \
  -e OPENAI_API_KEY=xxx \
  -e WEBFLOW_TOKEN=xxx \
  webflow-cms-automation
```

### ✅ Pros:
- Works anywhere Docker runs
- Consistent environment
- Easy local testing
- Portable between clouds
- Version controlled setup

### ❌ Cons:
- Requires Docker knowledge
- More manual setup for cloud
- Need to manage Chrome/ChromeDriver updates

### 📚 Documentation:
- Full Guide: [`DOCKER.md`](DOCKER.md)
- Scripts: `docker-run.sh` / `docker-run.bat`

---

## 🖥️ Option 2: Manual Server Deployment

**Best for:** Custom servers, existing infrastructure, full control

### Deploy manually:

```bash
# 1. Install Python 3.11+
python --version

# 2. Install Chrome/ChromeDriver
# Linux:
sudo apt-get install chromium-browser chromium-chromedriver

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export OPENAI_API_KEY=xxx
export WEBFLOW_TOKEN=xxx

# 5. Run with gunicorn
gunicorn server:app --bind 0.0.0.0:5000 --timeout 300
```

### ✅ Pros:
- Complete control
- No cloud costs
- Custom configuration
- Any server/OS

### ❌ Cons:
- Manual Chrome/ChromeDriver setup
- More maintenance
- Need to manage SSL
- Manual scaling

### 📚 Documentation:
- See [`README.md`](README.md) - "Production Deployment" section

---

## 📊 Comparison Table

| Feature | Docker | Manual |
|---------|--------|--------|
| **Setup Time** | 15 min ⚙️ | 30+ min 🔧 |
| **Ease of Use** | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Chrome Setup** | Auto ✅ | Manual ⚠️ |
| **Cost** | $0* | $0* |
| **Scaling** | Manual | Manual |
| **SSL/HTTPS** | Manual | Manual |
| **Monitoring** | DIY | DIY |
| **Best For** | Dev/Any Cloud | Custom Needs |

\* Infrastructure costs may apply

---

## 🎯 Decision Guide

### Choose Docker if:
- ✅ You want to run locally first
- ✅ You're deploying to AWS/GCP/Azure
- ✅ You need reproducible environments
- ✅ You know Docker already
- ✅ You want portability

### Choose Manual if:
- ✅ You have an existing server
- ✅ You need full control
- ✅ You have specific requirements
- ✅ You're comfortable with Linux admin
- ✅ You want zero cloud costs

---

## 🚦 Getting Started - Step by Step

### For Docker Users → Docker
1. Read: [`DOCKER.md`](DOCKER.md)
2. Run: `docker-compose up`
3. Test: `curl http://localhost:5000/health`

### For Server Admins → Manual
1. Read: [`README.md`](README.md) - Production section
2. Install Chrome + ChromeDriver
3. Install Python deps: `pip install -r requirements.txt`
4. Run: `gunicorn server:app`
5. Test: `curl http://localhost:5000/health`

---

## 📦 What's Included

All deployment methods include:
- ✅ Flask web server
- ✅ OpenAI GPT integration
- ✅ Selenium + Chrome for image scraping
- ✅ Webflow API integration
- ✅ Image analysis with AI vision
- ✅ Health check endpoint
- ✅ Webhook endpoint for automation

---

## 🔑 Required for All Methods

No matter which deployment method you choose, you need:

1. **OpenAI API Key**
   - Get from: https://platform.openai.com/api-keys
   - Set as: `OPENAI_API_KEY`

2. **Webflow API Token**
   - Get from: Webflow Account Settings → Integrations
   - Set as: `WEBFLOW_TOKEN`

---

## 🆘 Need Help?

| Issue | See Documentation |
|-------|-------------------|
| Docker deployment | [`DOCKER.md`](DOCKER.md) |
| General usage | [`README.md`](README.md) |

---

## 🎉 Ready to Deploy?

Pick your method above and follow the documentation. Both methods will get you to a working deployment!

**Recommended path for most users:**
1. Start with Docker for local testing
2. Deploy to production using Docker or manual setup
3. Choose based on your infrastructure needs

Good luck! 🚀

