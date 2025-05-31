# Installation Guide

## Prerequisites

- Ubuntu 20.04+ or Debian 10+
- Python 3.8 or higher
- Root access
- Network access to IPFIX/NetFlow sources

## Quick Installation

```bash
sudo ./install.sh
```

## Manual Installation Steps

1. **Install System Dependencies**
   ```bash
   sudo apt-get update
   sudo apt-get install python3 python3-pip python3-venv
   ```

2. **Install Python Dependencies**
   ```bash
   sudo pip3 install PyYAML netaddr
   ```

3. **Create Directories**
   ```bash
   sudo mkdir -p /opt/ipfix-enricher
   sudo mkdir -p /etc/ipfix-enricher
   sudo mkdir -p /var/log/ipfix-enricher
   ```

4. **Copy Files**
   ```bash
   sudo cp ipfix_enricher.py /opt/ipfix-enricher/
   sudo cp config/ipfix-enricher.yaml.example /etc/ipfix-enricher/config.yaml
   ```

5. **Install Services**
   ```bash
   sudo cp systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

6. **Configure**
   ```bash
   sudo nano /etc/ipfix-enricher/config.yaml
   ```

7. **Start Services**
   ```bash
   sudo systemctl enable ipfix-enricher
   sudo systemctl start ipfix-enricher
   ```

## Verification

Check that everything is running:
```bash
sudo systemctl status ipfix-enricher
telnet localhost 9999
```
