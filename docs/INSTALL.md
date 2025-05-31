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

## Post-Installation

### Verify Installation

1. **Check Service Status**
   ```bash
   sudo systemctl status ipfix-enricher
   ```

2. **Test Statistics Interface**
   ```bash
   telnet localhost 9999
   > stats
   > quit
   ```

3. **Monitor Initial Packets**
   ```bash
   ipfix-monitor
   ```

### Configure Flow Sources

1. **Cisco Router**
   ```
   flow-export version 9
   flow-export destination 10.0.0.10 2055
   ```

2. **Juniper Router**
   ```
   set forwarding-options sampling instance SAMPLE1 family inet output flow-server 10.0.0.10 port 2055 version-ipfix
   ```

### Configure Collectors

Update your flow collectors to receive from port 2056 instead of directly from routers.

### Performance Optimization

For high-traffic environments (>50k flows/sec):

1. **Increase System Limits**
   ```bash
   # /etc/sysctl.conf
   net.core.rmem_max = 134217728
   net.core.rmem_default = 134217728
   net.core.netdev_max_backlog = 5000
   ```

2. **CPU Affinity**
   ```bash
   # /etc/systemd/system/ipfix-enricher.service.d/override.conf
   [Service]
   CPUAffinity=2-7
   ```

3. **Increase Workers**
   ```yaml
   # /etc/ipfix-enricher/config.yaml
   performance:
     workers: 8
     queue_size: 100000
   ```

## Post-Installation

### Verify Installation

1. **Check Service Status**
   ```bash
   sudo systemctl status ipfix-enricher
   ```

2. **Test Statistics Interface**
   ```bash
   telnet localhost 9999
   > stats
   > quit
   ```

3. **Monitor Initial Packets**
   ```bash
   ipfix-monitor
   ```

### Configure Flow Sources

1. **Cisco Router**
   ```
   flow-export version 9
   flow-export destination 10.0.0.10 2055
   ```

2. **Juniper Router**
   ```
   set forwarding-options sampling instance SAMPLE1 family inet output flow-server 10.0.0.10 port 2055 version-ipfix
   ```

### Configure Collectors

Update your flow collectors to receive from port 2056 instead of directly from routers.

### Performance Optimization

For high-traffic environments (>50k flows/sec):

1. **Increase System Limits**
   ```bash
   # /etc/sysctl.conf
   net.core.rmem_max = 134217728
   net.core.rmem_default = 134217728
   net.core.netdev_max_backlog = 5000
   ```

2. **CPU Affinity**
   ```bash
   # /etc/systemd/system/ipfix-enricher.service.d/override.conf
   [Service]
   CPUAffinity=2-7
   ```

3. **Increase Workers**
   ```yaml
   # /etc/ipfix-enricher/config.yaml
   performance:
     workers: 8
     queue_size: 100000
   ```
