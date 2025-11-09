# Docker Deployment Guide

## Quick Start

### Windows

1. **Run the automated script:**
   ```cmd
   docker-run.bat
   ```

### Linux/macOS

1. **Run the automated script:**
   ```bash
   ./docker-run.sh
   ```

The script will:

- Create a `.env` file template if it doesn't exist
- Validate environment variables
- Build the Docker image
- Start the container
- Check health status

## Manual Docker Commands

### Build the Image

```bash
docker build -t webflow-cms-automation .
```

### Run the Container

```bash
docker run -d \
  --name webflow-cms-automation \
  -p 5000:5000 \
  -e OPENAI_API_KEY="your_key_here" \
  -e WEBFLOW_TOKEN="your_token_here" \
  -v "$(pwd)/content:/app/content" \
  -v "$(pwd)/best_match:/app/best_match" \
  --restart unless-stopped \
  webflow-cms-automation
```

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Container Management

### View Logs

```bash
docker logs -f webflow-cms-automation
```

### Stop Container

```bash
docker stop webflow-cms-automation
```

### Start Container

```bash
docker start webflow-cms-automation
```

### Restart Container

```bash
docker restart webflow-cms-automation
```

### Remove Container

```bash
docker rm -f webflow-cms-automation
```

### Access Container Shell

```bash
docker exec -it webflow-cms-automation /bin/bash
```

## Health Check

Check if the server is running:

```bash
curl http://localhost:5000/health
```

Expected response:

```json
{ "status": "ok" }
```

## Environment Variables

Create a `.env` file with:

```bash
OPENAI_API_KEY=sk-...
WEBFLOW_TOKEN=...
PORT=5000
```

## Volumes

The following directories are mounted as volumes to persist data:

- `./content` - Generated content files
- `./best_match` - Selected best match images

## Troubleshooting

### Container won't start

```bash
# Check container logs
docker logs webflow-cms-automation

# Check if port is already in use
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # Linux/macOS
```

### Chrome/ChromeDriver issues

The Docker image includes Chrome and ChromeDriver. If you see issues:

```bash
# Check Chrome version
docker exec webflow-cms-automation google-chrome --version

# Check ChromeDriver version
docker exec webflow-cms-automation chromedriver --version
```

### Out of memory

Add memory limits to docker run:

```bash
docker run -d \
  --memory="2g" \
  --memory-swap="2g" \
  ...
```

### Permission issues

Ensure mounted directories have proper permissions:

```bash
chmod -R 777 content best_match  # Linux/macOS
```

## Updating

To update the application:

```bash
# Stop and remove old container
docker stop webflow-cms-automation
docker rm webflow-cms-automation

# Rebuild image
docker build -t webflow-cms-automation .

# Start new container
docker run -d ...
```

Or simply run the automated script again:

```bash
./docker-run.sh  # or docker-run.bat on Windows
```

## Production Considerations

1. **Use docker-compose** for easier management
2. **Set up proper logging** driver
3. **Configure resource limits** (CPU, memory)
4. **Use secrets** for sensitive data instead of environment variables
5. **Set up monitoring** and alerts
6. **Use a reverse proxy** (nginx, traefik) for HTTPS
7. **Regular backups** of mounted volumes

## Multi-Container Setup

For production, consider using docker-compose with additional services:

```yaml
version: '3.8'

services:
  webflow-cms:
    build: .
    ...

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - webflow-cms

  redis:
    image: redis:alpine
    # For caching if needed
```

## Support

For issues specific to Docker deployment, check:

1. Docker daemon is running
2. Sufficient disk space
3. Network connectivity
4. Firewall settings
