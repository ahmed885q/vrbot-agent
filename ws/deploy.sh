#!/bin/bash
# VRBOT WebSocket Hub - Deployment Script
# Run on server: 65.109.214.187
# Usage: bash deploy.sh
set -e

echo "=== VRBOT WebSocket Hub - Deploying ==="

# 1. Install dependencies
echo "[1/6] Installing Python dependencies..."
pip3 install websockets --quiet 2>/dev/null || pip install websockets --quiet

# 2. Create hub directory
echo "[2/6] Setting up hub directory..."
HUB_DIR="/opt/vrbot/ws_hub"
mkdir -p "$HUB_DIR"
cp ws_hub.py "$HUB_DIR/ws_hub.py"
chmod +x "$HUB_DIR/ws_hub.py"

# 3. SSL certificate (Let's Encrypt)
echo "[3/6] Checking SSL certificate..."
if ! command -v certbot &> /dev/null; then
    echo "  Installing certbot..."
    apt-get update -qq && apt-get install -y -qq certbot > /dev/null 2>&1
fi

DOMAIN="ws.vrbot.me"
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"

if [ ! -f "$CERT_PATH" ]; then
    echo "  Obtaining SSL certificate for $DOMAIN..."
    certbot certonly --standalone --non-interactive --agree-tos \
        --email ahmed885q@gmail.com \
        -d "$DOMAIN" \
        --preferred-challenges http
    echo "  SSL certificate obtained!"
else
    echo "  SSL certificate already exists."
fi

# 4. Create systemd service (SSL on port 443)
echo "[4/6] Creating systemd service..."
cat > /etc/systemd/system/vrbot-ws-hub.service << 'EOF'
[Unit]
Description=VRBOT WebSocket Hub
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vrbot/ws_hub
ExecStart=/usr/bin/python3 /opt/vrbot/ws_hub/ws_hub.py --port 443 --ssl
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=false
ProtectSystem=false

[Install]
WantedBy=multi-user.target
EOF

# 5. Fallback service on port 8765 (no SSL)
cat > /etc/systemd/system/vrbot-ws-hub-fallback.service << 'EOF'
[Unit]
Description=VRBOT WebSocket Hub (non-SSL fallback)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vrbot/ws_hub
ExecStart=/usr/bin/python3 /opt/vrbot/ws_hub/ws_hub.py --port 8765
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 6. Start services
echo "[5/6] Starting services..."
systemctl daemon-reload
systemctl enable vrbot-ws-hub.service
systemctl restart vrbot-ws-hub.service
systemctl enable vrbot-ws-hub-fallback.service
systemctl restart vrbot-ws-hub-fallback.service

echo "[6/6] Verifying..."
sleep 2

if systemctl is-active --quiet vrbot-ws-hub.service; then
    echo "  WSS Hub (port 443) - RUNNING"
else
    echo "  WSS Hub (port 443) - FAILED (check: journalctl -u vrbot-ws-hub -n 20)"
fi

if systemctl is-active --quiet vrbot-ws-hub-fallback.service; then
    echo "  WS Hub (port 8765) - RUNNING"
else
    echo "  WS Hub (port 8765) - FAILED"
fi

echo ""
echo "=== Deployment Complete ==="
echo "  WSS: wss://ws.vrbot.me/ws (port 443)"
echo "  WS:  ws://ws.vrbot.me:8765/ws"
echo "  Health: curl http://localhost:8765/health"
echo "  Logs: journalctl -u vrbot-ws-hub -f"
