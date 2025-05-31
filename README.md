# IPFIX AS Enricher

A high-performance packet processor that enriches IPFIX and NetFlow v9 flow data with Autonomous System (AS) information extracted directly from the flow packets.

## What is this project?

This project acts as a transparent proxy for IPFIX/NetFlow traffic. It sits between your network devices (routers, switches) and your flow collectors, extracting AS numbers from the flow data and enriching the packets before forwarding them.

### The Problem

- Network flow data (IPFIX/NetFlow) contains valuable information about traffic patterns
- AS numbers help identify the networks that traffic originates from or goes to
- Many flow collectors don't extract or properly handle AS information
- Manual AS lookups are time-consuming and don't scale

### The Solution

IPFIX AS Enricher:
- **Intercepts** flow packets from network devices
- **Extracts** AS numbers directly from NetFlow v9 and IPFIX packets
- **Enriches** the data with additional AS information
- **Forwards** enhanced packets to your existing collectors
- **Monitors** everything in real-time

## Architecture

```
+-----------------+                    +------------------+                    +-----------------+
¦ Network Device  ¦  IPFIX/NetFlow v9  ¦ IPFIX AS Enricher¦   Enriched Flow    ¦ Flow Collector  ¦
¦ (Router/Switch) ¦ -----------------> ¦   (Port 2055)    ¦ -----------------> ¦  (Port 2056)    ¦
+-----------------+                    ¦                  ¦                    +-----------------+
                                       ¦  AS Extraction   ¦
                                       ¦  Engine          ¦
                                       ¦                  ¦
                                       ¦ Statistics API   ¦
                                       ¦  (Port 9999)     ¦
                                       +------------------+
                                                ¦
                                                v
                                       +------------------+
                                       ¦ Monitoring Tools ¦
                                       ¦ - ipfix-monitor  ¦
                                       ¦ - ipfix-stats    ¦
                                       ¦ - ipfix-tail     ¦
                                       +------------------+
```

## Key Features

### 1. **Multi-Protocol Support**
- **IPFIX** (IP Flow Information Export) - RFC 7011
- **NetFlow v9** - Cisco's flexible flow export format
- Automatic protocol detection
- Template-aware processing for NetFlow v9

### 2. **AS Number Extraction**
- Extracts source and destination AS numbers from flow records
- Handles various NetFlow v9 template formats
- Fallback mechanisms for non-standard implementations
- Caches AS information for performance

### 3. **High Performance**
- Asynchronous packet processing
- Zero-copy forwarding where possible
- Configurable worker threads
- Handles 100,000+ flows/second

### 4. **Real-time Monitoring**
- Telnet interface for live statistics (port 9999)
- Packet rate monitoring
- AS number distribution
- Template tracking for NetFlow v9
- Error and drop counters

### 5. **Production Ready**
- Systemd service integration
- Automatic restart on failure
- Log rotation support
- Configurable nice levels for CPU priority

## Monitoring Tools

The project includes several monitoring utilities:

### ipfix-monitor
Real-time packet flow monitor showing live traffic
```bash
ipfix-monitor
# Shows: timestamp, source IP:port, packet size, protocol version, extracted AS numbers
```

### ipfix-stats
Statistics dashboard with auto-refresh
```bash
ipfix-stats
# Displays: packet rates, AS statistics, top talkers, errors
```

### ipfix-tail
Enhanced log viewer with color coding
```bash
ipfix-tail
# Follows logs with highlighting for errors, AS numbers, and important events
```

### ipfix-status
Quick status check utility
```bash
ipfix-status
# Shows: service status, key metrics, recent errors
```

### Telnet Statistics Interface
Direct access to internal statistics
```bash
telnet localhost 9999

Available commands:
> stats         # General statistics
> as_stats      # AS number frequency
> templates     # NetFlow v9 templates
> help          # Command list
> quit          # Exit
```

## Installation

### Prerequisites
- Ubuntu 20.04+ or Debian 10+
- Python 3.8 or higher
- Root access for service installation
- Network access to flow sources

### Quick Install
```bash
git clone https://github.com/paolokappa/ipfix-as-enricher.git
cd ipfix-as-enricher
sudo ./install.sh
```

### Configuration
Edit `/etc/ipfix-enricher/config.yaml`:
```yaml
general:
  listen_port: 2055      # Where to receive flows
  output_port: 2056      # Where to send enriched flows
  stats_port: 9999       # Telnet statistics port

enrichment:
  as_extraction: true    # Enable AS extraction
  
forwarding:
  collectors:
    - host: 127.0.0.1    # Your flow collector
      port: 2056
```

### Start Service
```bash
sudo systemctl start ipfix-enricher
sudo systemctl enable ipfix-enricher
```

## Use Cases

### 1. **Network Security**
- Identify traffic from suspicious AS numbers
- Track communications with specific networks
- Build AS-based traffic profiles

### 2. **Traffic Engineering**
- Analyze traffic distribution by AS
- Optimize peering arrangements
- Capacity planning based on AS patterns

### 3. **Compliance & Reporting**
- Track data flows to specific countries/regions
- Generate AS-based traffic reports
- Monitor communications with sanctioned networks

### 4. **Troubleshooting**
- Quickly identify which AS is causing issues
- Track routing changes via AS path analysis
- Debug peering problems

## Performance Tuning

For high-traffic environments:

```yaml
performance:
  workers: 8           # Increase worker threads
  queue_size: 50000    # Larger packet queue
  buffer_size: 65535   # Maximum UDP buffer
```

## Troubleshooting

### No packets received
```bash
# Check if packets arrive
sudo tcpdump -i any -n port 2055

# Verify firewall
sudo iptables -L -n | grep 2055

# Check service logs
sudo journalctl -u ipfix-enricher -f
```

### High CPU usage
- Reduce worker threads
- Enable flow sampling on router
- Check for packet loops

### AS numbers not extracted
- Verify NetFlow v9 templates include AS fields
- Check if router exports AS information
- Use ipfix-monitor to inspect packets

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file.

## Author

Paolo Kappa - 2024

## Acknowledgments

- NetFlow v9 format by Cisco Systems
- IPFIX standards by IETF
- Python asyncio for high-performance networking
