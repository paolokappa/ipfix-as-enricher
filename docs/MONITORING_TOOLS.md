# Monitoring Tools Guide

IPFIX AS Enricher includes a comprehensive suite of monitoring tools to help you understand and troubleshoot your flow data in real-time.

## Overview of Tools

| Tool | Purpose | Usage |
|------|---------|--------|
| ipfix-monitor | Real-time packet viewer | Debugging, verification |
| ipfix-stats | Statistics dashboard | Performance monitoring |
| ipfix-tail | Log viewer | Troubleshooting |
| ipfix-status | Quick health check | Operational monitoring |
| telnet interface | Direct statistics access | Automation, scripting |

## Detailed Tool Documentation

### ipfix-monitor

**Purpose**: Real-time visualization of flow packets as they're processed

**Features**:
- Color-coded output for easy reading
- Shows packet source, size, and protocol
- Displays extracted AS numbers
- Highlights errors and anomalies

**Usage**:
```bash
# Basic usage - show all packets
ipfix-monitor

# Filter specific source
ipfix-monitor --source 192.168.1.1

# Show only packets with AS info
ipfix-monitor --with-as

# Increase verbosity
ipfix-monitor -v
```

**Output Example**:
```
2024-05-31 10:23:45 | 192.168.1.1:2055 | 1384 bytes | NetFlow v9 | AS: 15169->13335
2024-05-31 10:23:45 | 192.168.1.1:2055 | 1344 bytes | NetFlow v9 | AS: 8075->20940
2024-05-31 10:23:46 | 192.168.1.2:2055 | 584 bytes  | IPFIX      | AS: 3356->16509
```

**Color Coding**:
- Green: Successfully processed packets
- Yellow: Packets without AS information
- Red: Processing errors
- Blue: IPFIX packets
- Cyan: NetFlow v9 packets

### ipfix-stats

**Purpose**: Live statistics dashboard with auto-refresh

**Features**:
- Packet rates (current and average)
- Top AS numbers by frequency
- Protocol distribution
- Error counters
- Memory usage

**Usage**:
```bash
# Default view (auto-refresh every 1s)
ipfix-stats

# Slower refresh rate
ipfix-stats --interval 5

# One-time snapshot
ipfix-stats --once

# Export to JSON
ipfix-stats --json > stats.json
```

**Dashboard Sections**:

1. **General Statistics**
   - Uptime
   - Total packets processed
   - Current packet rate
   - Average packet rate

2. **AS Statistics**
   - Unique AS numbers seen
   - Top 10 source AS
   - Top 10 destination AS
   - AS pairs frequency

3. **Protocol Breakdown**
   - NetFlow v9 packets
   - IPFIX packets
   - Unknown packets
   - Error percentage

4. **Performance Metrics**
   - CPU usage
   - Memory usage
   - Queue depth
   - Drop rate

### ipfix-tail

**Purpose**: Enhanced log viewer with intelligent filtering and highlighting

**Features**:
- Follows logs in real-time
- Color highlighting for important events
- Regex filtering support
- Multiple log level viewing

**Usage**:
```bash
# Follow all logs
ipfix-tail

# Show only errors
ipfix-tail --errors

# Filter for specific AS
ipfix-tail --grep "AS.*15169"

# Show last 100 lines
ipfix-tail -n 100

# Follow specific log file
ipfix-tail /var/log/ipfix-enricher/debug.log
```

**Highlighting**:
- AS numbers in bold
- Errors in red
- Warnings in yellow
- Info in default color
- Debug in gray

### ipfix-status

**Purpose**: Quick operational status check

**Features**:
- Service status
- Key metrics summary
- Recent errors
- Configuration validation

**Usage**:
```bash
# Basic status
ipfix-status

# Detailed status
ipfix-status -v

# JSON output for monitoring systems
ipfix-status --json

# Nagios/Icinga compatible output
ipfix-status --nagios
```

**Output Includes**:
- Service state (running/stopped)
- Uptime
- Packets processed in last minute
- Current memory usage
- Last 5 errors (if any)
- Configuration issues

### Telnet Statistics Interface

**Purpose**: Direct programmatic access to internal statistics

**Features**:
- Simple text protocol
- Real-time statistics
- Scriptable interface
- No authentication (bind to localhost only)

**Usage**:
```bash
# Interactive session
telnet localhost 9999

# Scripted usage
echo "stats" | nc localhost 9999

# Get AS statistics
(echo "as_stats"; sleep 1) | telnet localhost 9999
```

**Available Commands**:

| Command | Description | Output |
|---------|-------------|---------|
| stats | General statistics | Packets, rates, uptime |
| as_stats | AS number frequencies | Top AS numbers with counts |
| templates | NetFlow v9 templates | Template IDs and fields |
| errors | Recent errors | Last 10 errors with timestamps |
| config | Active configuration | Current settings |
| help | Command list | Available commands |
| quit | Close connection | - |

**Example Session**:
```
$ telnet localhost 9999
Connected to localhost.
> stats
Uptime: 2d 14h 23m
Total packets: 145,234,891
Current rate: 12,453 pkt/s
Bytes processed: 125.4 GB
Active AS numbers: 4,521

> as_stats
Top Source AS:
  AS15169 (Google): 2,345,123
  AS13335 (Cloudflare): 1,234,567
  AS16509 (Amazon): 987,654
  
Top Destination AS:
  AS32934 (Facebook): 3,456,789
  AS8075 (Microsoft): 2,345,678
  
> quit
Connection closed.
```

## Integration with Monitoring Systems

### Prometheus Metrics

If Prometheus support is enabled:
```bash
curl http://localhost:9100/metrics
```

Metrics include:
- `ipfix_packets_total`
- `ipfix_bytes_total`
- `ipfix_as_unique`
- `ipfix_errors_total`

### Nagios/Icinga Check

```bash
#!/bin/bash
# check_ipfix_enricher.sh

STATUS=$(ipfix-status --nagios)
EXIT_CODE=$?

echo "$STATUS"
exit $EXIT_CODE
```

### Zabbix Integration

Use the JSON output from tools:
```bash
ipfix-stats --json | jq '.packet_rate'
```

## Best Practices

1. **Regular Monitoring**
   - Set up alerts for packet rate drops
   - Monitor error rates
   - Track AS number diversity

2. **Troubleshooting Workflow**
   1. Check status: `ipfix-status`
   2. Review errors: `ipfix-tail --errors`
   3. Watch live traffic: `ipfix-monitor`
   4. Analyze statistics: `telnet localhost 9999`

3. **Performance Monitoring**
   - Use `ipfix-stats` during peak hours
   - Set up Prometheus for historical data
   - Alert on queue depth increases

4. **Security**
   - Restrict telnet interface to localhost
   - Use firewall rules for stats port
   - Regularly review AS statistics for anomalies
