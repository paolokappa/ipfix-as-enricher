#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPFIX Enricher Statistics Viewer
Simple text-based stats viewer for ipfix-enricher
"""

import time
import re
import os
import sys
import argparse
from datetime import datetime

class IPFIXStats:
    def __init__(self, log_file='/var/log/ipfix-enricher/ipfix-enricher.log', refresh_rate=5):
        self.log_file = log_file
        self.refresh_rate = refresh_rate
        self.running = True
        
        # Color codes
        self.colors = {
            'RED': '\033[0;31m',
            'GREEN': '\033[0;32m',
            'YELLOW': '\033[1;33m',
            'BLUE': '\033[0;34m',
            'CYAN': '\033[0;36m',
            'NC': '\033[0m'  # No Color
        }
        
    def get_last_stats_block(self):
        """Extract the last statistics block from log file"""
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Find all statistics blocks
            blocks = re.split(r'={50,}', content)
            
            # Find the last block containing "Statistics:"
            for block in reversed(blocks):
                if 'Statistics:' in block:
                    return block
                    
            return None
            
        except Exception as e:
            return None
            
    def parse_stats(self, stats_block):
        """Parse statistics from the block"""
        if not stats_block:
            return {}
            
        metrics = {}
        
        # Define patterns
        patterns = {
            'timestamp': r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]',
            'uptime': r'Uptime: (\d+)s',
            'mtu': r'MTU: (\d+) bytes',
            'success_rate': r'Sent: .* \(([\d.]+)% success\)',
            'pps_in': r'Processed: .* \(([\d.]+) pps',
            'mbps_in': r'Processed: .* ([\d.]+) Mbps\)',
            'pps_out': r'Rate: ([\d.]+) pps',
            'mbps_out': r'Rate: .* ([\d.]+) Mbps',
            'enrichment': r'Enriched: .* \(([\d.]+)%\)',
            'match_rate': r'Total match rate: ([\d.]+)%',
            'errors': r'Errors: ([\d,]+)',
            'buffer': r'Current size: (\d+)',
            'buffer_peak': r'Peak size: (\d+)',
            'memory': r'Memory: RSS ([\d.]+) MB',
            'processed': r'Processed: ([\d,]+) packets',
            'sent': r'Sent: ([\d,]+)',
            'oversized': r'Oversized dropped: ([\d,]+)',
            'buffer_dropped': r'Buffer dropped: ([\d,]+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, stats_block)
            if match:
                value = match.group(1)
                # Remove commas for numeric values
                if key in ['errors', 'processed', 'sent', 'oversized', 'buffer_dropped']:
                    value = value.replace(',', '')
                metrics[key] = value
                
        return metrics
        
    def get_color_for_value(self, value, good_threshold, warning_threshold, reverse=False):
        """Get color based on value and thresholds"""
        try:
            val = float(value)
            if reverse:
                if val <= good_threshold:
                    return self.colors['GREEN']
                elif val <= warning_threshold:
                    return self.colors['YELLOW']
                else:
                    return self.colors['RED']
            else:
                if val >= good_threshold:
                    return self.colors['GREEN']
                elif val >= warning_threshold:
                    return self.colors['YELLOW']
                else:
                    return self.colors['RED']
        except:
            return self.colors['NC']
            
    def get_recent_errors(self):
        """Get recent error messages from log"""
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            errors = []
            for line in reversed(lines):
                if 'ERROR' in line or 'WARNING' in line:
                    # Clean and truncate line
                    clean_line = line.strip()
                    if len(clean_line) > 80:
                        clean_line = clean_line[:77] + '...'
                    errors.append(clean_line)
                    
                    if len(errors) >= 3:
                        break
                        
            return list(reversed(errors))
            
        except:
            return []
            
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
        
    def format_uptime(self, seconds):
        """Format uptime in human readable format"""
        try:
            s = int(seconds)
            hours = s // 3600
            minutes = (s % 3600) // 60
            secs = s % 60
            return f"{hours}h {minutes}m {secs}s"
        except:
            return "0h 0m 0s"
            
    def display_stats(self, metrics):
        """Display formatted statistics"""
        self.clear_screen()
        
        # Header
        print(f"{self.colors['BLUE']}IPFIX Enricher Stats - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{self.colors['NC']}")
        print("=" * 60)
        
        if not metrics:
            print("\nWaiting for statistics...")
            return
            
        # Basic info
        if 'uptime' in metrics:
            uptime_str = self.format_uptime(metrics['uptime'])
            print(f"\nUptime: {self.colors['CYAN']}{uptime_str}{self.colors['NC']}")
            
        # Success rate
        if 'success_rate' in metrics:
            success_rate = float(metrics['success_rate'])
            color = self.get_color_for_value(success_rate, 90, 70)
            print(f"\nSuccess Rate: {color}{success_rate:.1f}%{self.colors['NC']}")
            
        # Traffic
        print("\nTraffic:")
        if 'pps_in' in metrics:
            print(f"  In:  {metrics['pps_in']} pps", end='')
            if 'mbps_in' in metrics:
                print(f" / {metrics['mbps_in']} Mbps")
            else:
                print()
                
        if 'pps_out' in metrics:
            print(f"  Out: {metrics['pps_out']} pps", end='')
            if 'mbps_out' in metrics:
                print(f" / {metrics['mbps_out']} Mbps")
            else:
                print()
                
        # Enrichment
        if 'enrichment' in metrics:
            enrich_rate = float(metrics['enrichment'])
            color = self.get_color_for_value(enrich_rate, 95, 80)
            print(f"  Enrichment: {color}{enrich_rate:.1f}%{self.colors['NC']}")
            
        if 'match_rate' in metrics:
            match_rate = float(metrics['match_rate'])
            color = self.get_color_for_value(match_rate, 95, 80)
            print(f"  Pattern Match: {color}{match_rate:.1f}%{self.colors['NC']}")
            
        # Errors and drops
        print("\nHealth:")
        if 'errors' in metrics:
            errors = int(metrics['errors'])
            color = self.get_color_for_value(errors, 10, 100, reverse=True)
            print(f"  Errors: {color}{errors:,}{self.colors['NC']}")
            
        if 'buffer' in metrics:
            buffer = int(metrics['buffer'])
            color = self.get_color_for_value(buffer, 1000, 5000, reverse=True)
            print(f"  Buffer: {color}{buffer:,}{self.colors['NC']}", end='')
            if 'buffer_peak' in metrics:
                print(f" (peak: {metrics['buffer_peak']})")
            else:
                print()
                
        if 'oversized' in metrics:
            oversized = int(metrics['oversized'])
            if oversized > 0:
                print(f"  Oversized dropped: {self.colors['YELLOW']}{oversized:,}{self.colors['NC']}")
                
        if 'buffer_dropped' in metrics:
            dropped = int(metrics['buffer_dropped'])
            if dropped > 0:
                print(f"  Buffer dropped: {self.colors['RED']}{dropped:,}{self.colors['NC']}")
                
        if 'memory' in metrics:
            print(f"  Memory: {metrics['memory']} MB")
            
        # Counts
        print("\nCounts:")
        if 'processed' in metrics:
            print(f"  Processed: {int(metrics['processed']):,} packets")
        if 'sent' in metrics:
            print(f"  Sent: {int(metrics['sent']):,} packets")
            
        # Recent errors
        if 'errors' in metrics and int(metrics['errors']) > 0:
            recent_errors = self.get_recent_errors()
            if recent_errors:
                print(f"\n{self.colors['YELLOW']}Recent Errors:{self.colors['NC']}")
                for error in recent_errors:
                    print(f"  {error}")
                    
        # Alerts
        alerts = []
        if 'success_rate' in metrics and float(metrics['success_rate']) < 50:
            alerts.append(f"{self.colors['RED']}? ALERT: Low success rate!{self.colors['NC']}")
        if 'buffer' in metrics and int(metrics['buffer']) > 5000:
            alerts.append(f"{self.colors['YELLOW']}? WARNING: High buffer usage!{self.colors['NC']}")
        if 'errors' in metrics and int(metrics['errors']) > 1000:
            alerts.append(f"{self.colors['RED']}? ALERT: High error count!{self.colors['NC']}")
            
        if alerts:
            print("\nAlerts:")
            for alert in alerts:
                print(f"  {alert}")
                
    def run(self):
        """Main loop"""
        print(f"{self.colors['BLUE']}IPFIX Enricher Stats - Refresh every {self.refresh_rate}s (Ctrl+C to exit){self.colors['NC']}")
        print("=" * 60)
        
        try:
            while self.running:
                stats_block = self.get_last_stats_block()
                metrics = self.parse_stats(stats_block)
                self.display_stats(metrics)
                
                print(f"\n{'-'*60}")
                print(f"Refreshing in {self.refresh_rate} seconds...")
                
                time.sleep(self.refresh_rate)
                
        except KeyboardInterrupt:
            print(f"\n\n{self.colors['BLUE']}Exiting...{self.colors['NC']}")
            
def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='IPFIX Enricher Statistics Viewer')
    parser.add_argument('refresh_rate', 
                       nargs='?', 
                       type=int, 
                       default=5,
                       help='Refresh rate in seconds (default: 5)')
    parser.add_argument('-l', '--log-file',
                       default='/var/log/ipfix-enricher/ipfix-enricher.log',
                       help='Path to log file')
    args = parser.parse_args()
    
    # Check if log file exists
    if not os.path.exists(args.log_file):
        print(f"Error: Log file not found: {args.log_file}")
        sys.exit(1)
        
    # Create and run stats viewer
    stats = IPFIXStats(args.log_file, args.refresh_rate)
    stats.run()
    
if __name__ == '__main__':
    main()
