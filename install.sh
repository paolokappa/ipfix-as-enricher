#!/bin/bash

# IPFIX AS Enricher Installer

set -e

echo "=================================="
echo "IPFIX AS Enricher Installer"
echo "=================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p /opt/ipfix-enricher
mkdir -p /etc/ipfix-enricher
mkdir -p /var/log/ipfix-enricher

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv python3-dev

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Copy files
echo "Copying files..."
cp ipfix_enricher.py /opt/ipfix-enricher/
chmod +x /opt/ipfix-enricher/ipfix_enricher.py

# Copy scripts
cp -r scripts/* /opt/ipfix-enricher/
chmod +x /opt/ipfix-enricher/*.py
chmod +x /opt/ipfix-enricher/*.sh

# Create symlinks for easy access
echo "Creating command shortcuts..."
ln -sf /opt/ipfix-enricher/ipfix-monitor.py /usr/local/bin/ipfix-monitor
ln -sf /opt/ipfix-enricher/ipfix-stats.py /usr/local/bin/ipfix-stats
ln -sf /opt/ipfix-enricher/ipfix-tail.py /usr/local/bin/ipfix-tail
ln -sf /opt/ipfix-enricher/ipfix-status /usr/local/bin/ipfix-status

# Copy configuration
echo "Installing configuration..."
if [ ! -f /etc/ipfix-enricher/config.yaml ]; then
    cp config/ipfix-enricher.yaml.example /etc/ipfix-enricher/config.yaml
    echo "Created config file: /etc/ipfix-enricher/config.yaml"
    echo "Please edit this file before starting the service"
fi

# Install systemd services
echo "Installing systemd services..."
cp systemd/*.service /etc/systemd/system/
systemctl daemon-reload

# Create log rotation
echo "Setting up log rotation..."
cat > /etc/logrotate.d/ipfix-enricher << 'LOGROTATE'
/var/log/ipfix-enricher/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    postrotate
        systemctl reload ipfix-enricher >/dev/null 2>&1 || true
    endscript
}
LOGROTATE

echo ""
echo "=================================="
echo "Installation completed!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit configuration: nano /etc/ipfix-enricher/config.yaml"
echo "2. Start service: systemctl start ipfix-enricher"
echo "3. Enable on boot: systemctl enable ipfix-enricher"
echo "4. Check status: systemctl status ipfix-enricher"
echo ""
echo "Monitoring commands available:"
echo "- ipfix-monitor : Real-time packet monitor"
echo "- ipfix-stats   : Statistics viewer"
echo "- ipfix-tail    : Log viewer"
echo "- ipfix-status  : Quick status check"
echo ""
