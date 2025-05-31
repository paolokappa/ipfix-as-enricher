#!/bin/bash
# IPFIX Traffic Monitor - Real-time monitoring of NetEngine to SolarWinds flow
# Author: IPFIX Enricher Monitor
# Version: 1.0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
NETENGINE_IP="185.54.80.2"
ENRICHER_IP="185.54.81.23"
SOLARWINDS_IP="185.54.81.20"
IPFIX_PORT="9996"
REFRESH_INTERVAL=5

# Temp files for statistics
STATS_FILE="/tmp/ipfix_stats_$$"
PREV_STATS_FILE="/tmp/ipfix_prev_stats_$$"

# Cleanup on exit
trap cleanup EXIT
cleanup() {
    rm -f "$STATS_FILE" "$PREV_STATS_FILE"
    echo -e "\n${YELLOW}Monitor stopped${NC}"
    exit 0
}

# Clear screen and show header
show_header() {
    clear
    echo -e "${BOLD}${CYAN}-----------------------------------------------------------------------${NC}"
    echo -e "${BOLD}${CYAN}                    IPFIX ENRICHER TRAFFIC MONITOR                      ${NC}"
    echo -e "${BOLD}${CYAN}-----------------------------------------------------------------------${NC}"
    echo -e "${GREEN}NetEngine${NC} (${NETENGINE_IP}) ? ${BLUE}Enricher${NC} (${ENRICHER_IP}) ? ${YELLOW}SolarWinds${NC} (${SOLARWINDS_IP})"
    echo -e "Port: ${IPFIX_PORT} | Refresh: ${REFRESH_INTERVAL}s | Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${CYAN}-----------------------------------------------------------------------${NC}\n"
}

# Get packet counts from tcpdump
get_packet_stats() {
    # Save previous stats
    if [ -f "$STATS_FILE" ]; then
        cp "$STATS_FILE" "$PREV_STATS_FILE"
    fi
    
    # Capture packets for interval
    timeout $REFRESH_INTERVAL tcpdump -nn -i any \
        "(src $NETENGINE_IP and dst $ENRICHER_IP and port $IPFIX_PORT) or \
         (src $NETENGINE_IP and dst $SOLARWINDS_IP and port $IPFIX_PORT)" \
        2>/dev/null | while read line; do
        if echo "$line" | grep -q "$ENRICHER_IP.$IPFIX_PORT"; then
            echo "IN" >> "$STATS_FILE"
        elif echo "$line" | grep -q "$SOLARWINDS_IP.$IPFIX_PORT"; then
            echo "OUT" >> "$STATS_FILE"
        fi
    done &
    
    wait
}

# Calculate statistics
calculate_stats() {
    local in_count=0
    local out_count=0
    local prev_in=0
    local prev_out=0
    
    if [ -f "$STATS_FILE" ]; then
        in_count=$(grep -c "IN" "$STATS_FILE" 2>/dev/null || echo 0)
        out_count=$(grep -c "OUT" "$STATS_FILE" 2>/dev/null || echo 0)
    fi
    
    if [ -f "$PREV_STATS_FILE" ]; then
        prev_in=$(grep -c "IN" "$PREV_STATS_FILE" 2>/dev/null || echo 0)
        prev_out=$(grep -c "OUT" "$PREV_STATS_FILE" 2>/dev/null || echo 0)
    fi
    
    # Calculate rates
    local in_rate=$((in_count / REFRESH_INTERVAL))
    local out_rate=$((out_count / REFRESH_INTERVAL))
    
    # Display stats
    echo -e "${BOLD}CURRENT INTERVAL (last ${REFRESH_INTERVAL}s):${NC}"
    echo -e "  ${GREEN}Received from NetEngine:${NC}  ${in_count} packets (${in_rate} pps)"
    echo -e "  ${YELLOW}Sent to SolarWinds:${NC}      ${out_count} packets (${out_rate} pps)"
    
    # Success rate
    if [ $in_count -gt 0 ]; then
        local success_rate=$((out_count * 100 / in_count))
        echo -e "  ${CYAN}Forward Success Rate:${NC}     ${success_rate}%"
    fi
    
    echo ""
}

# Get enricher service stats
get_enricher_stats() {
    echo -e "${BOLD}ENRICHER SERVICE STATUS:${NC}"
    
    # Service status
    local service_status=$(systemctl is-active ipfix-enricher 2>/dev/null)
    if [ "$service_status" = "active" ]; then
        echo -e "  Service: ${GREEN}? Active${NC}"
    else
        echo -e "  Service: ${RED}? Inactive${NC}"
    fi
    
    # Get last stats from journal
    local last_stats=$(journalctl -u ipfix-enricher -n 50 --no-pager 2>/dev/null | \
        grep -E "Processed:|Rate:|Data:" | tail -6)
    
    if [ -n "$last_stats" ]; then
        echo -e "  ${BOLD}Last Statistics:${NC}"
        echo "$last_stats" | while read line; do
            echo "    $line"
        done
    fi
    
    echo ""
}

# Get iptables counters
get_iptables_stats() {
    echo -e "${BOLD}FIREWALL COUNTERS:${NC}"
    
    # CSF allow rule
    local csf_stats=$(iptables -L ALLOWIN -n -v 2>/dev/null | grep "185.54.80.0/22" | head -1)
    if [ -n "$csf_stats" ]; then
        local packets=$(echo "$csf_stats" | awk '{print $1}')
        local bytes=$(echo "$csf_stats" | awk '{print $2}')
        echo -e "  CSF Allow Rule: ${GREEN}${packets} packets, ${bytes} bytes${NC}"
    fi
    
    # NAT rule
    local nat_stats=$(iptables -t nat -L POSTROUTING -n -v 2>/dev/null | grep "185.54.81.23.*185.54.81.20")
    if [ -n "$nat_stats" ]; then
        local nat_packets=$(echo "$nat_stats" | awk '{print $1}')
        echo -e "  NAT SNAT Rule:  ${YELLOW}${nat_packets} packets${NC}"
    fi
    
    echo ""
}

# Check connectivity
check_connectivity() {
    echo -e "${BOLD}CONNECTIVITY TEST:${NC}"
    
    # Ping test
    for ip in $NETENGINE_IP $SOLARWINDS_IP; do
        if ping -c 1 -W 1 $ip >/dev/null 2>&1; then
            echo -e "  Ping $ip: ${GREEN}? OK${NC}"
        else
            echo -e "  Ping $ip: ${RED}? Failed${NC}"
        fi
    done
    
    # Port test
    if netstat -unlp 2>/dev/null | grep -q ":$IPFIX_PORT"; then
        echo -e "  Port $IPFIX_PORT: ${GREEN}? Listening${NC}"
    else
        echo -e "  Port $IPFIX_PORT: ${RED}? Not listening${NC}"
    fi
    
    echo ""
}

# Main monitoring loop
main() {
    # Initial cleanup
    rm -f "$STATS_FILE" "$PREV_STATS_FILE"
    
    echo -e "${YELLOW}Starting IPFIX Traffic Monitor...${NC}"
    echo -e "Press ${RED}Ctrl+C${NC} to stop\n"
    sleep 2
    
    while true; do
        show_header
        
        # Start packet capture in background
        get_packet_stats
        
        # While capturing, show other stats
        get_enricher_stats
        get_iptables_stats
        check_connectivity
        
        # Wait for capture to complete
        sleep $REFRESH_INTERVAL
        
        # Calculate and show packet stats
        calculate_stats
        
        echo -e "${CYAN}-----------------------------------------------------------------------${NC}"
        echo -e "Refreshing in ${REFRESH_INTERVAL}s... Press Ctrl+C to stop"
    done
}

# Check requirements
check_requirements() {
    local missing=""
    
    for cmd in tcpdump iptables systemctl journalctl ping netstat; do
        if ! command -v $cmd >/dev/null 2>&1; then
            missing="$missing $cmd"
        fi
    done
    
    if [ -n "$missing" ]; then
        echo -e "${RED}Error: Missing required commands:${missing}${NC}"
        echo "Please install the missing tools and try again."
        exit 1
    fi
    
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Warning: This script works best when run as root (for tcpdump)${NC}"
        echo "Some features may not work correctly."
        sleep 3
    fi
}

# Start monitoring
check_requirements
main
