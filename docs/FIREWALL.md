# Firewall Configuration Guide

This guide helps you configure your firewall to work with IPFIX AS Enricher and avoid common issues, especially with CSF.

## Required Ports

| Port | Protocol | Direction | Purpose | Source |
|------|----------|-----------|---------|---------|
| 2055 | UDP | Inbound | Receive IPFIX/NetFlow | Network devices |
| 2056 | UDP | Outbound | Forward enriched data | To collectors |
| 9999 | TCP | Inbound | Statistics interface | Localhost only |

**Note**: Some installations use custom ports (e.g., 9996). Adjust accordingly.

## CSF (ConfigServer Security & Firewall) - CRITICAL CONFIGURATION

**?? WARNING**: CSF has several gotchas that can break IPFIX forwarding!

### CSF Common Problems and Solutions

#### Problem 1: UDP_OUT is empty or restrictive
By default, CSF might have:
```
UDP_OUT = ""
```
This blocks ALL outbound UDP traffic!

**Solution**:
```bash
sudo nano /etc/csf/csf.conf

# Change from:
UDP_OUT = ""

# To (allow all UDP out):
UDP_OUT = "1:65535"

# Or specific ports:
UDP_OUT = "53,123,2056,9996"
```

#### Problem 2: Missing inbound ports
CSF won't allow traffic unless explicitly listed:

```bash
# In /etc/csf/csf.conf
# Add your IPFIX ports to UDP_IN:
UDP_IN = "20,21,53,123,2055,2056,9996,10000,12320,33434:33523"

# If using telnet stats remotely, add to TCP_IN:
TCP_IN = "20,21,22,25,80,179,443,465,587,9999,10000"
```

#### Problem 3: Service start order
CSF can override iptables rules added by other services!

**Solution**: Ensure proper systemd ordering:

1. Edit `/etc/systemd/system/ipfix-nat.service`:
```ini
[Unit]
Description=IPFIX NAT and Firewall Rules
After=network.target
Before=csf.service          # CRITICAL: Run before CSF!

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/path/to/your/nat-rules.sh
# CSF will start after this, so our rules are applied first

[Install]
WantedBy=multi-user.target
```

2. Edit `/etc/systemd/system/ipfix-enricher.service`:
```ini
[Unit]
Description=IPFIX AS Enricher Service
After=network.target csf.service    # Start AFTER CSF is loaded
Wants=network-online.target
```

#### Problem 4: CSF Connection Tracking
CSF might block return UDP traffic even with ports open.

**Solution**:
```bash
# In /etc/csf/csf.conf
# Enable connection tracking for UDP:
CT_LIMIT = "0"              # Disable CT limits
CONNLIMIT = ""              # Remove connection limits
UDP_TIMEOUT = "30"          # Increase UDP timeout
```

### Complete CSF Configuration Example

```bash
# 1. Edit CSF config
sudo nano /etc/csf/csf.conf

# 2. Update these lines:
TCP_IN = "20,21,22,25,80,179,443,465,587,3323,9999,10000"
TCP_OUT = "1:65535"
UDP_IN = "20,21,53,123,2055,2056,9996,10000"
UDP_OUT = "1:65535"    # CRITICAL - Must not be empty!

# 3. If using specific IPs only:
# Allow your routers
sudo csf -a 192.168.1.1 comment "Router IPFIX"
sudo csf -a 10.0.0.1 comment "Switch NetFlow"

# Allow your collectors  
sudo csf -a 10.0.0.100 comment "Flow collector"

# 4. Restart CSF
sudo csf -r

# 5. Verify rules are applied
sudo iptables -L -n -v | grep -E "(2055|2056|9996)"
```

### Testing CSF Configuration

```bash
# 1. Temporarily disable CSF to test
sudo csf -x

# 2. Test IPFIX flow
# (Your packets should work now)

# 3. Re-enable CSF
sudo csf -e

# 4. If packets stop, check CSF logs
sudo tail -f /var/log/lfd.log
sudo grep -i drop /var/log/messages
```

## iptables (Without CSF)

For systems without CSF, use standard iptables:

```bash
# Input rules
sudo iptables -A INPUT -p udp --dport 2055 -j ACCEPT
sudo iptables -A INPUT -p udp --dport 9996 -j ACCEPT  # If using port 9996
sudo iptables -A INPUT -p tcp -s 127.0.0.1 --dport 9999 -j ACCEPT

# Output rules (important!)
sudo iptables -A OUTPUT -p udp --dport 2056 -j ACCEPT
sudo iptables -A OUTPUT -p udp --sport 2055 -j ACCEPT  # Allow responses

# NAT rules if needed
sudo iptables -t nat -A POSTROUTING -p udp -s 185.54.81.23 -d 185.54.81.20 --dport 9996 -j SNAT --to-source 185.54.80.2:40000

# Save rules
sudo iptables-save > /etc/iptables/rules.v4
```

## Custom Port Configuration

If using non-standard ports (like 9996):

1. **Update enricher config**:
```yaml
# /etc/ipfix-enricher/config.yaml
general:
  listen_port: 9996    # Instead of 2055
  output_port: 9996    # Instead of 2056
```

2. **Update firewall rules** accordingly:
```bash
# Replace 2055/2056 with your ports
sudo iptables -A INPUT -p udp --dport 9996 -j ACCEPT
```

## NAT Service for Complex Routing

The `ipfix-nat.service` handles complex NAT scenarios:

```bash
# Example /etc/systemd/system/ipfix-nat.service
[Unit]
Description=IPFIX NAT and Firewall Rules
After=network.target
Before=csf.service

[Service]
Type=oneshot
RemainAfterExit=yes

# Input rules
ExecStart=/bin/bash -c 'iptables -A INPUT -p udp -s 185.54.80.2 --dport 9996 -j ACCEPT'

# NAT rules for source IP modification
ExecStart=/bin/bash -c 'iptables -t nat -A POSTROUTING -p udp -s 185.54.81.23 -d 185.54.81.20 --dport 9996 -j SNAT --to-source 185.54.80.2:40000'

# Cleanup on stop
ExecStop=/bin/bash -c 'iptables -D INPUT -p udp -s 185.54.80.2 --dport 9996 -j ACCEPT 2>/dev/null || true'
ExecStop=/bin/bash -c 'iptables -t nat -D POSTROUTING -p udp -s 185.54.81.23 -d 185.54.81.20 --dport 9996 -j SNAT --to-source 185.54.80.2:40000 2>/dev/null || true'

[Install]
WantedBy=multi-user.target
```

## Debugging Firewall Issues

### Step-by-step debugging:

```bash
# 1. Check what's listening
sudo netstat -nlup | grep -E "(2055|2056|9996|9999)"

# 2. Monitor packets in real-time
sudo tcpdump -i any -n port 9996 or port 2055

# 3. Check iptables counters
watch -n 1 'sudo iptables -L -n -v | grep -E "(2055|9996|DROP)"'

# 4. Check CSF denies
sudo csf -g YOUR_ROUTER_IP
sudo csf -t

# 5. Check if CSF is blocking UDP out
sudo iptables -L OUTPUT -n -v | grep DROP
```

### Common CSF Error Messages

- **"Dropped by CSF"**: Check UDP_IN and UDP_OUT settings
- **"Connection tracking table full"**: Increase CT_LIMIT or disable
- **"Rate limited"**: Check CT_LIMIT and CONNLIMIT settings

## Security Recommendations

1. **Restrict sources** (don't allow all IPs):
```bash
# Only from specific routers
iptables -A INPUT -p udp -s 192.168.1.0/24 --dport 2055 -j ACCEPT
iptables -A INPUT -p udp --dport 2055 -j DROP
```

2. **Use CSF allow lists**:
```bash
# Instead of opening ports globally
sudo csf -a 192.168.1.1 comment "Router1 IPFIX"
```

3. **Monitor for attacks**:
```bash
# Add rate limiting
iptables -A INPUT -p udp --dport 2055 -m limit --limit 10000/s -j ACCEPT
```
