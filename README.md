# Webflow CMS Automation

Automated content generation and publishing system for Webflow CMS. This service generates marketing dashboard entries using OpenAI GPT, scrapes and selects relevant images using AI vision, and automatically publishes them to your Webflow collection.

## Features

- 🤖 **AI Content Generation** - Generate high-quality dashboard entries using OpenAI GPT-4
- 🖼️ **Intelligent Image Selection** - Automatically scrape images from URLs and use AI vision to select the best match
- 🔄 **Webhook Integration** - RESTful API for easy integration with external systems
- 📦 **Webflow Publishing** - Automatic creation and publishing of CMS items
- 🎯 **Smart Field Mapping** - Flexible mapping between generated content and Webflow collection fields
- ⚡ **Batch Processing** - Generate and publish multiple items in a single request

## Architecture

The system consists of several key components:

1. **Flask Server** (`server.py`) - Webhook endpoint that orchestrates the entire workflow
2. **Content Generator** (`chatgpt_to_webflow.py`) - GPT-powered content generation
3. **Image Scraper** (`scrape_images_js.py`) - Selenium-based image extraction from web pages
4. **Image Selector** (`select_best_image.py`) - AI vision-powered image ranking and selection
5. **Webflow Uploader** (`upload_mock_image.py`) - Image upload to Webflow assets

## Requirements

- Python 3.8+
- Chrome/Chromium browser (for Selenium)
- OpenAI API key
- Webflow API token with CMS write permissions
- Webflow collection ID and site ID

## Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Webflow-CMS-Automation
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install ChromeDriver

The image scraper requires ChromeDriver for Selenium:

**Linux (Ubuntu/Debian):**

```bash
sudo apt-get update
sudo apt-get install chromium-browser chromium-chromedriver
```

**macOS:**

```bash
brew install --cask chromedriver
```

**Windows:**
Download from https://chromedriver.chromium.org/ and add to PATH

### 4. Configure environment variables

Create a `.env` file in the project root:

```bash
# Required for Webhook Server (server.py)
OPENAI_API_KEY=sk-...
WEBFLOW_TOKEN=...

# Optional
PORT=5000

# Note: collection_id and site_id are provided in the webhook request payload
# They are NOT needed as environment variables for server.py
```

**For standalone CLI usage** (`chatgpt_to_webflow.py`):

```bash
# Additional variables needed for CLI tool only
WEBFLOW_COLLECTION_ID=...
WEBFLOW_SITE_ID=...
```

### Quick Reference: What Needs What?

| Use Case                         | Required Environment Variables                              |
| -------------------------------- | ----------------------------------------------------------- |
| **Webhook Server** (`server.py`) | `OPENAI_API_KEY`, `WEBFLOW_TOKEN`                           |
| **CLI Generate**                 | `OPENAI_API_KEY`                                            |
| **CLI Publish**                  | `WEBFLOW_TOKEN`, `WEBFLOW_COLLECTION_ID`, `WEBFLOW_SITE_ID` |

## Configuration Files

### collection*schema*\*.json

Automatically generated when the server receives a webhook. Contains the Webflow collection schema for field validation.

### site_id.json

Optional. Maps site names to Webflow site IDs for easier management.

### tag-map.json

Maps tag labels to Webflow tag item IDs for multi-reference fields:

```json
{
  "marketing": "tag-id-1",
  "analytics": "tag-id-2"
}
```

### webflow-fields.json

Custom field mapping between generated content and Webflow field slugs:

```json
{
  "title": "name",
  "subtitle": "subtitle",
  "source": "source-name",
  "link": "source-url",
  "thumbnail": "thumbnail"
}
```

## Usage

### Starting the Server

```bash
python server.py
```

The server will start on `http://0.0.0.0:5000` (or the port specified in `PORT` env var).

### Webhook Endpoint

**POST** `/webhook`

Generate content, scrape images, and publish to Webflow.

**Request Body:**

```json
{
  "collection_id": "690901e88bb9a020259fa715",
  "site_id": "6753c21daa8e43df9660c5f5",
  "fieldData": {
    "slug": "marketing-analytics",
    "category": "Marketing"
  },
  "count": 5
}
```

**Parameters:**

- `collection_id` (required) - Webflow collection ID
- `site_id` (required) - Webflow site ID for publishing
- `fieldData` (required) - Object containing:
  - `slug` or `category` (required) - Topic for content generation
  - Other fields will be included in the generated items
- `count` (optional) - Number of items to generate (default: 5, max: 15)

**Response:**

```json
{
  "success": true,
  "message": "Generated and processed 5 items",
  "topic": "marketing-analytics",
  "content_dir": "content/20251109_142530_marketing-analytics",
  "summary": {
    "total": 5,
    "created": 4,
    "skipped": 1,
    "failed": 0
  },
  "results": [
    {
      "item": "Google Ads Performance Dashboard",
      "status": "created",
      "item_id": "67...",
      "thumbnail_url": "https://...",
      "image_score": 95
    }
  ]
}
```

### Health Check Endpoint

**GET** `/health`

Returns server status:

```json
{
  "status": "ok"
}
```

## Workflow

1. **Receive Webhook** - Server receives POST request with topic and configuration
2. **Generate Content** - OpenAI GPT generates dashboard entries with metadata
3. **For Each Generated Item:**
   - Extract the source URL from the generated content
   - Scrape images from the URL using Selenium
   - Analyze images using GPT Vision to find best match (or skip if only 1 image)
   - Upload selected image to Webflow assets
   - Map fields to Webflow collection schema
   - Create CMS item in Webflow
4. **Publish** - Publish all created items to make them live
5. **Return Results** - Summary of created, skipped, and failed items

## Image Selection Logic

- **0 images found** → Skip item (not created)
- **1 image found** → Use directly (skip AI analysis)
- **2+ images found** → Use AI vision to rank and select best match

The AI scorer evaluates images based on:

- Relevance to keywords
- Visual quality
- Content appropriateness
- Professional appearance

## Command-Line Tools

### Generate Content Only

Generate dashboard entries without publishing:

```bash
# Requires: OPENAI_API_KEY
python chatgpt_to_webflow.py generate "marketing analytics" --count 5 --output dashboards.json
```

### Publish Existing Content

Publish previously generated content:

```bash
# Requires: WEBFLOW_TOKEN, WEBFLOW_COLLECTION_ID, WEBFLOW_SITE_ID (or --site-id flag)
python chatgpt_to_webflow.py publish dashboards.json --live --field-map webflow-fields.json --tag-map tag-map.json
```

Alternatively, pass collection and site IDs via command line to avoid environment variables:

```bash
export WEBFLOW_TOKEN=...
python chatgpt_to_webflow.py publish dashboards.json --live --site-id YOUR_SITE_ID
```

### Verify Setup

Check environment configuration:

```bash
python verify_setup.py
```

## Directory Structure

```
.
├── server.py                 # Main webhook server
├── chatgpt_to_webflow.py    # Content generation and publishing
├── scrape_images_js.py      # Selenium-based image scraper
├── select_best_image.py     # AI image selection
├── upload_mock_image.py     # Webflow image uploader
├── verify_setup.py          # Configuration validator
├── requirements.txt         # Python dependencies
├── collection_schema_*.json # Auto-generated Webflow schema
├── site_id.json            # Site ID mapping
├── tag-map.json            # Tag ID mapping
├── webflow-fields.json     # Field mapping configuration
├── content/                # Generated content (auto-created)
├── images/                 # Temporary scraped images (auto-created)
└── best_match/            # Selected images (auto-created)
```

## Error Handling

The system includes robust error handling:

- **No images found** - Item is skipped with warning
- **Failed image analysis** - Uses best available or skips
- **Webflow API errors** - Logged and returned in response
- **Invalid URLs** - Logged and item is skipped
- **Rate limits** - Implements timeout and retry logic

## Logging

All operations are logged with appropriate levels:

- `INFO` - Normal operations and progress
- `WARNING` - Recoverable issues (no images, skipped items)
- `ERROR` - Failures that prevent item creation

## Production Deployment

### 🆓 FREE Cloud Hosting (No Credit Card Required) ⭐ **EASIEST**

Deploy to **Render.com** or other free platforms - **no payment method needed!**

**[➡️ See FREE_HOSTING_OPTIONS.md for all free platforms](FREE_HOSTING_OPTIONS.md)**

**Quick Deploy to Render.com** (5 minutes, completely free):

1. Push code to GitHub
2. Sign up at [Render.com](https://render.com) (free, no credit card)
3. New Web Service → Connect your repo
4. Add env vars: `OPENAI_API_KEY`, `WEBFLOW_TOKEN`
5. Deploy! ✅

**[📖 Full Render.com Guide](RENDER_DEPLOYMENT.md)** | **[🆓 All Free Options](FREE_HOSTING_OPTIONS.md)**

**Other Free Platforms:**

- Railway.app - Easy setup, $5 monthly credit
- Fly.io - Global deployment
- **All details:** [FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md)

---

### 🖥️ Custom Server Deployment

For deploying on your own server with full control:

1. Set all required environment variables
2. Ensure ChromeDriver is installed and in PATH
3. Configure firewall to allow incoming connections on your port
4. Use a process manager (systemd, supervisor, PM2)

### Running with systemd

Create `/etc/systemd/system/webflow-cms.service`:

```ini
[Unit]
Description=Webflow CMS Automation
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/Webflow-CMS-Automation
Environment="OPENAI_API_KEY=sk-..."
Environment="WEBFLOW_TOKEN=..."
Environment="PORT=5000"
ExecStart=/usr/bin/python3 server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable webflow-cms
sudo systemctl start webflow-cms
sudo systemctl status webflow-cms
```

### Using Docker

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5000
EXPOSE 5000

CMD ["python", "server.py"]
```

Build and run:

```bash
docker build -t webflow-cms-automation .
docker run -d -p 5000:5000 \
  -e OPENAI_API_KEY=sk-... \
  -e WEBFLOW_TOKEN=... \
  -e PORT=5000 \
  webflow-cms-automation
```

**Note:** `collection_id` and `site_id` are provided in the webhook request, not as environment variables.

### Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

## API Rate Limits

Be aware of API limits:

- **OpenAI API** - Varies by plan (monitor token usage)
- **Webflow API** - 60 requests per minute

The system handles multiple API calls per item:

- 1 call for content generation
- 1-N calls for image analysis (depends on images found)
- 1 call per item creation
- 1 call for batch publishing

## Security Considerations

1. **Environment Variables** - Never commit API keys to version control
2. **Webhook Authentication** - Consider adding authentication to `/webhook` endpoint
3. **Input Validation** - Validate all webhook payload fields
4. **Rate Limiting** - Consider implementing rate limiting on endpoints
5. **HTTPS** - Always use HTTPS in production with valid SSL certificate

## Troubleshooting

### ChromeDriver Issues

```bash
# Check ChromeDriver version
chromedriver --version

# Check Chrome version
google-chrome --version

# They must match major version
```

### Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Webflow API Errors

- Verify token has correct permissions
- Check collection ID is correct
- Ensure site ID matches your Webflow site
- Review collection schema for required fields

### Image Scraping Fails

- Check if URL is accessible
- Verify site doesn't block automated access
- Try with `headless=False` for debugging
- Check if JavaScript is required to load images

## Support

For issues, questions, or contributions, please contact the development team or open an issue in the repository.

## License

Proprietary - All rights reserved.
