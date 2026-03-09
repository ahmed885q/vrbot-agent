#!/bin/bash
# cloud.vrbot.me - Setup Script
# Run on Hetzner Dedicated Server: 88.99.64.19
# Sets up Nginx + SSL for cloud.vrbot.me
set -e

echo "=== cloud.vrbot.me - Setting up ==="

DOMAIN="cloud.vrbot.me"

# 1. Install Nginx
echo "[1/5] Installing Nginx..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx > /dev/null 2>&1
echo "  Nginx installed"

# 2. Create Nginx config
echo "[2/5] Configuring Nginx..."
cat > /etc/nginx/sites-available/cloud.vrbot.me << 'NGINX_CONF'
server {
    listen 80;
    server_name cloud.vrbot.me;

    location /health {
        return 200 '{"status":"ok","server":"cloud.vrbot.me"}';
        add_header Content-Type application/json;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
NGINX_CONF

ln -sf /etc/nginx/sites-available/cloud.vrbot.me /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t

# 3. Start Nginx
echo "[3/5] Starting Nginx..."
systemctl enable nginx
systemctl restart nginx
echo "  Nginx running on port 80"

# 4. SSL Certificate
echo "[4/5] Setting up SSL..."
certbot --nginx --non-interactive --agree-tos \
    --email ahmed885q@gmail.com \
    -d "$DOMAIN" \
    --redirect 2>/dev/null || echo "  SSL setup failed (will retry manually)"

# 5. Check what apps are available
echo "[5/5] Checking for existing applications..."

if command -v node &> /dev/null; then
    echo "  Node.js: $(node --version)"
else
    echo "  Node.js not installed - installing..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs > /dev/null 2>&1
    echo "  Node.js: $(node --version)"
fi

if command -v docker &> /dev/null; then
    echo "  Docker: $(docker --version | head -1)"
    echo "  Running containers:"
    docker ps --format "  - {{.Names}}: {{.Status}}" 2>/dev/null || echo "  (none)"
fi

echo ""
echo "=== Setup Complete ==="
echo "  Nginx is running on cloud.vrbot.me"
echo "  Next: Deploy the cloud dashboard app on port 3000"
echo "  SSL will auto-redirect HTTP to HTTPS"
