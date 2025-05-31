# Configuration Guide

## Configuration File

The main configuration file is located at `/etc/ipfix-enricher/config.yaml`.

## Configuration Options

### General Settings

```yaml
general:
  listen_port: 2055        # Port to receive IPFIX/NetFlow
  output_port: 2056        # Port to send enriched data
  stats_port: 9999         # Telnet statistics port
  log_level: INFO          # DEBUG, INFO, WARNING, ERROR
```

### Enrichment Options

```yaml
enrichment:
  as_extraction: true      # Enable AS number extraction
  geoip_enabled: false     # Enable GeoIP lookups
  reverse_dns: false       # Enable reverse DNS
```

### Performance Tuning

```yaml
performance:
  workers: 4               # Number of worker threads
  queue_size: 10000        # Internal queue size
  buffer_size: 65535       # UDP buffer size
```

### Forwarding Configuration

```yaml
forwarding:
  collectors:
    - host: 127.0.0.1
      port: 2056
    - host: collector2.example.com
      port: 9996
```

## Network Configuration

### Firewall Rules

Allow incoming IPFIX/NetFlow:
```bash
sudo ufw allow 2055/udp
```

Allow statistics access (restrict source IP):
```bash
sudo ufw allow from 192.168.1.0/24 to any port 9999
```

### NAT Configuration

The `ipfix-nat.service` handles special NAT rules if needed.
Edit `/etc/systemd/system/ipfix-nat.service` to customize.
