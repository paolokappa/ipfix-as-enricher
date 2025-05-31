# IPFIX AS Enricher

A high-performance IPFIX and NetFlow v9 packet enricher that extracts and adds AS (Autonomous System) information to flow data.

## Features

- **Multi-Protocol Support**: Handles both IPFIX and NetFlow v9 protocols
- **AS Number Extraction**: Automatically extracts AS numbers from flow packets
- **High Performance**: Asynchronous packet processing with configurable workers
- **Real-time Statistics**: Telnet interface for monitoring (port 9999)
- **Flexible Forwarding**: Forward enriched data to multiple collectors
- **Service Management**: Systemd integration for reliable operation
- **Monitoring Tools**: Included utilities for real-time monitoring and statistics

## Architecture

```
[Router/Switch] --IPFIX/NetFlow--> [IPFIX Enricher:2055] --Enriched--> [Collector:2056]
                                            |
                                            v
                                    [AS Extraction Engine]
                                            |
                                            v
                                    [Statistics:9999]
```

## Requirements

- Python 3.8 or higher
- Ubuntu 20.04+ or Debian 10+
- systemd for service management
- Root access for installation

## Installation

### Quick Install

```bash
git clone https://github.com/paolokappa/ipfix-as-enricher.git
cd ipfix-as-enricher
sudo ./install.sh
```

### Manual Install

1. Install dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv
sudo pip3 install -r requirements.txt
```

2. Copy files:
```bash
sudo cp ipfix_enricher.py /opt/ipfix-enricher/
sudo cp systemd/*.service /etc/systemd/system/
```

3. Configure:
```bash
sudo cp config/ipfix-enricher.yaml.example /etc/ipfix-enricher/config.yaml
sudo nano /etc/ipfix-enricher/config.yaml
```

4. Enable services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ipfix-enricher
sudo systemctl enable ipfix-nat  # If using NAT rules
sudo systemctl start ipfix-enricher
```

## Configuration

Edit `/etc/ipfix-enricher/config.yaml` to configure:
- Listen and forward ports
- AS extraction options
- Performance tuning
- Collector destinations

See `config/ipfix-enricher.yaml.example` for all options.

## Usage

### Service Management

```bash
# Start/stop/restart
sudo systemctl start ipfix-enricher
sudo systemctl stop ipfix-enricher
sudo systemctl restart ipfix-enricher

# Check status
sudo systemctl status ipfix-enricher

# View logs
sudo journalctl -u ipfix-enricher -f
```

### Monitoring Tools

```bash
# Real-time packet monitor
ipfix-monitor

# Statistics dashboard
ipfix-stats

# Tail enricher logs
ipfix-tail

# Quick status check
ipfix-status
```

### Telnet Statistics Interface

```bash
telnet localhost 9999

Available commands:
- stats         : Show general statistics
- as_stats      : Show AS number statistics  
- templates     : Show NetFlow v9 templates
- help          : Show available commands
- quit          : Exit
```

## Performance

The enricher is designed for high-throughput environments:
- Processes 100,000+ flows/second on modern hardware
- Low latency (<1ms added delay)
- Memory efficient with streaming processing
- Configurable worker threads for scaling

## Troubleshooting

### Service won't start
- Check logs: `sudo journalctl -u ipfix-enricher -n 50`
- Verify config: `python3 /opt/ipfix-enricher/ipfix_enricher.py --test`
- Check port availability: `sudo netstat -nlup | grep 2055`

### No packets received
- Verify firewall rules: `sudo iptables -L -n`
- Check routing: `ip route show`
- Test with tcpdump: `sudo tcpdump -i any -n port 2055`

### High CPU usage
- Reduce worker threads in config
- Check for packet loops
- Enable flow sampling on router

## File Structure

```
ipfix-as-enricher/
+-- ipfix_enricher.py       # Main application
+-- install.sh              # Installation script
+-- requirements.txt        # Python dependencies
+-- config/                 # Configuration files
¦   +-- ipfix-enricher.yaml.example
+-- systemd/                # Service definitions
¦   +-- ipfix-enricher.service
¦   +-- ipfix-nat.service
+-- scripts/                # Utility scripts
¦   +-- ipfix-monitor.py    # Packet monitor
¦   +-- ipfix-stats.py      # Statistics viewer
¦   +-- ipfix-tail.py       # Log tailer
¦   +-- ipfix-status        # Status checker
+-- docs/                   # Documentation
```

## Contributing

Pull requests are welcome! Please read CONTRIBUTING.md first.

## License

MIT License - see LICENSE file for details.

## Author

Paolo Kappa - 2024
