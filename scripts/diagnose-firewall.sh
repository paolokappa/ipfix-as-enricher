#!/bin/bash

# IPFIX Enricher Firewall Diagnostic Tool

echo "=== IPFIX Enricher Firewall Diagnostics ==="
echo "Date: $(date)"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (sudo)${NC}"
    exit 1
fi

# 1. Check listening ports
echo "1. Checking listening ports..."
PORTS=$(netstat -nlup | grep -E "(2055|2056|9996|9999)")
if [ -z "$PORTS" ]; then
    echo -e "${RED}? No IPFIX ports listening${NC}"
else
    echo -e "${GREEN}? Listening ports:${NC}"
    echo "$PORTS"
fi
echo ""

# 2. Check CSF status
echo "2. Checking CSF (ConfigServer Firewall)..."
if command -v csf &> /dev/null; then
    echo -e "${YELLOW}CSF is installed${NC}"
    
    # Check UDP_OUT
    UDP_OUT=$(grep "^UDP_OUT" /etc/csf/csf.conf | cut -d'"' -f2)
    if [ -z "$UDP_OUT" ]; then
        echo -e "${RED}? CRITICAL: UDP_OUT is empty - blocks all outbound UDP!${NC}"
        echo "  Fix: Set UDP_OUT = \"1:65535\" in /etc/csf/csf.conf"
    else
        echo -e "${GREEN}? UDP_OUT configured: $UDP_OUT${NC}"
    fi
    
    # Check UDP_IN for IPFIX ports
    UDP_IN=$(grep "^UDP_IN" /etc/csf/csf.conf | cut -d'"' -f2)
    if ! echo "$UDP_IN" | grep -qE "(2055|9996)"; then
        echo -e "${YELLOW}? IPFIX ports not in UDP_IN${NC}"
        echo "  Current UDP_IN: $UDP_IN"
        echo "  Add your IPFIX port (2055 or 9996) to UDP_IN"
    else
        echo -e "${GREEN}? IPFIX ports found in UDP_IN${NC}"
    fi
else
    echo -e "${GREEN}? CSF not installed${NC}"
fi
echo ""

# 3. Check iptables rules
echo "3. Checking iptables rules..."
echo "INPUT rules for IPFIX:"
iptables -L INPUT -n -v | grep -E "(2055|2056|9996|9999)" || echo "  No INPUT rules found"
echo ""
echo "OUTPUT rules:"
OUTPUT_DROPS=$(iptables -L OUTPUT -n -v | grep DROP | grep -v "0     0")
if [ ! -z "$OUTPUT_DROPS" ]; then
    echo -e "${RED}? OUTPUT DROP rules found:${NC}"
    echo "$OUTPUT_DROPS"
else
    echo -e "${GREEN}? No OUTPUT DROP rules${NC}"
fi
echo ""

# 4. Check NAT rules
echo "4. Checking NAT rules..."
NAT_RULES=$(iptables -t nat -L -n -v | grep -E "(2055|9996|SNAT|DNAT)" | grep -v "0     0")
if [ ! -z "$NAT_RULES" ]; then
    echo "Active NAT rules:"
    echo "$NAT_RULES"
else
    echo "No NAT rules for IPFIX"
fi
echo ""

# 5. Test packet flow
echo "5. Testing packet reception (5 seconds)..."
TESTFILE="/tmp/ipfix_test_$$"
timeout 5 tcpdump -i any -n -c 1 port 2055 or port 9996 > $TESTFILE 2>&1 &
TCPDUMP_PID=$!
sleep 5

if grep -q "1 packet captured" $TESTFILE; then
    echo -e "${GREEN}? Packets detected on IPFIX port${NC}"
else
    echo -e "${YELLOW}? No packets detected in 5 seconds${NC}"
    echo "  Possible causes:"
    echo "  - No flows being sent by routers"
    echo "  - Firewall blocking before tcpdump"
    echo "  - Wrong port configured"
fi
rm -f $TESTFILE
echo ""

# 6. Check service status
echo "6. Checking services..."
if systemctl is-active --quiet ipfix-enricher; then
    echo -e "${GREEN}? ipfix-enricher service is running${NC}"
else
    echo -e "${RED}? ipfix-enricher service is not running${NC}"
fi

if systemctl is-active --quiet ipfix-nat; then
    echo -e "${GREEN}? ipfix-nat service is running${NC}"
else
    echo -e "${YELLOW}? ipfix-nat service is not running${NC}"
fi
echo ""

# 7. Quick stats check
echo "7. Checking enricher statistics..."
STATS=$(timeout 2 echo "stats" | nc localhost 9999 2>/dev/null)
if [ ! -z "$STATS" ]; then
    echo -e "${GREEN}? Statistics accessible${NC}"
    echo "$STATS" | head -5
else
    echo -e "${RED}? Cannot access statistics on port 9999${NC}"
fi
echo ""

# Summary
echo "=== SUMMARY ==="
echo "Run this command to see live packet flow:"
echo "  sudo tcpdump -i any -n port 2055 or port 9996"
echo ""
echo "To temporarily disable CSF for testing:"
echo "  sudo csf -x  # disable"
echo "  # test your flows"
echo "  sudo csf -e  # re-enable"
echo ""
echo "For more details, see: docs/FIREWALL.md"
