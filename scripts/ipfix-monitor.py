#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPFIX Enricher Real-time Monitor
Interactive dashboard for monitoring ipfix-enricher performance
"""

import curses
import time
import re
import os
import sys
import subprocess
from collections import deque
from datetime import datetime
import argparse
import signal

class IPFIXMonitor:
    def __init__(self, log_file='/var/log/ipfix-enricher/ipfix-enricher.log'):
        self.log_file = log_file
        self.running = True
        
        # Stats storage
        self.current_stats = {}
        self.history = {
            'timestamps': deque(maxlen=300),  # 5 minutes of 1-second samples
            'success_rate': deque(maxlen=300),
            'pps_in': deque(maxlen=300),
            'pps_out': deque(maxlen=300),
            'enrichment_rate': deque(maxlen=300),
            'errors': deque(maxlen=300),
            'buffer_size': deque(maxlen=300),
        }
        
        # Alert thresholds
        self.alerts = {
            'success_rate_low': 50,
            'buffer_high': 5000,
            'error_rate_high': 100,
        }
        
        # Active alerts
        self.active_alerts = []
        
        # Last log position
        self.last_position = 0
        
        # Colors
        self.colors = {}
        
    def init_colors(self):
        """Initialize color pairs"""
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Good
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Warning
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)     # Error
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Info
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK)   # Normal
        curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_BLACK)    # Header
        
        self.colors = {
            'good': curses.color_pair(1),
            'warning': curses.color_pair(2),
            'error': curses.color_pair(3),
            'info': curses.color_pair(4),
            'normal': curses.color_pair(5),
            'header': curses.color_pair(6),
        }
        
    def parse_log_line(self, line):
        """Parse statistics from log line"""
        # Look for statistics blocks
        if "Statistics:" in line:
            return {'stats_start': True}
            
        # Parse various metrics
        patterns = {
            'uptime': r'Uptime: (\d+)s',
            'mtu': r'MTU: (\d+) bytes',
            'ipv4_matches': r'IPv4 matches: ([\d,]+) packets',
            'ipv6_matches': r'IPv6 matches: ([\d,]+) packets',
            'match_rate': r'Total match rate: ([\d.]+)%',
            'as_replaced': r'AS replaced: ([\d,]+) times',
            'processed': r'Processed: ([\d,]+) packets \(([\d.]+) pps, ([\d.]+) Mbps\)',
            'enriched': r'Enriched: ([\d,]+) \(([\d.]+)%\)',
            'sent': r'Sent: ([\d,]+) \(([\d.]+)% success\)',
            'oversized': r'Oversized dropped: ([\d,]+)',
            'buffer_dropped': r'Buffer dropped: ([\d,]+)',
            'errors': r'Errors: ([\d,]+)',
            'forward_rate': r'Rate: ([\d.]+) pps, ([\d.]+) Mbps',
            'buffer_current': r'Current size: (\d+)',
            'buffer_peak': r'Peak size: (\d+)',
            'memory': r'Memory: RSS ([\d.]+) MB',
            'error_detail': r'(\w+): (\d+)',
        }
        
        results = {}
        
        for key, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                if key == 'processed':
                    results['processed'] = int(match.group(1).replace(',', ''))
                    results['pps_in'] = float(match.group(2))
                    results['mbps_in'] = float(match.group(3))
                elif key == 'enriched':
                    results['enriched'] = int(match.group(1).replace(',', ''))
                    results['enrichment_rate'] = float(match.group(2))
                elif key == 'sent':
                    results['sent'] = int(match.group(1).replace(',', ''))
                    results['success_rate'] = float(match.group(2))
                elif key == 'forward_rate':
                    results['pps_out'] = float(match.group(1))
                    results['mbps_out'] = float(match.group(2))
                elif key in ['uptime', 'mtu', 'buffer_current', 'buffer_peak']:
                    results[key] = int(match.group(1))
                elif key in ['ipv4_matches', 'ipv6_matches', 'as_replaced', 'oversized', 'buffer_dropped', 'errors']:
                    results[key] = int(match.group(1).replace(',', ''))
                elif key in ['match_rate', 'memory']:
                    results[key] = float(match.group(1))
                elif key == 'error_detail' and 'error_types' not in results:
                    results['error_types'] = {}
                    results['error_types'][match.group(1)] = int(match.group(2))
                    
        return results
        
    def read_latest_stats(self):
        """Read latest statistics from log file"""
        try:
            if not os.path.exists(self.log_file):
                return
                
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to last position
                f.seek(self.last_position)
                
                stats_block = []
                in_stats = False
                
                for line in f:
                    parsed = self.parse_log_line(line)
                    
                    if parsed.get('stats_start'):
                        in_stats = True
                        stats_block = []
                    elif in_stats and '=' * 40 in line and stats_block:
                        # End of stats block, process it
                        for stat_line in stats_block:
                            stat_data = self.parse_log_line(stat_line)
                            self.current_stats.update({k: v for k, v in stat_data.items() if v is not None})
                        in_stats = False
                        
                        # Update history
                        timestamp = datetime.now()
                        self.history['timestamps'].append(timestamp)
                        self.history['success_rate'].append(self.current_stats.get('success_rate', 0))
                        self.history['pps_in'].append(self.current_stats.get('pps_in', 0))
                        self.history['pps_out'].append(self.current_stats.get('pps_out', 0))
                        self.history['enrichment_rate'].append(self.current_stats.get('enrichment_rate', 0))
                        self.history['errors'].append(self.current_stats.get('errors', 0))
                        self.history['buffer_size'].append(self.current_stats.get('buffer_current', 0))
                        
                    elif in_stats:
                        stats_block.append(line)
                        
                # Save position
                self.last_position = f.tell()
                
        except Exception as e:
            pass
            
    def check_alerts(self):
        """Check for alert conditions"""
        self.active_alerts = []
        
        # Check success rate
        success_rate = self.current_stats.get('success_rate', 100)
        if success_rate < self.alerts['success_rate_low']:
            self.active_alerts.append(f"LOW SUCCESS RATE: {success_rate:.1f}%")
            
        # Check buffer size
        buffer_size = self.current_stats.get('buffer_current', 0)
        if buffer_size > self.alerts['buffer_high']:
            self.active_alerts.append(f"HIGH BUFFER: {buffer_size} packets")
            
        # Check error rate
        if len(self.history['errors']) > 1:
            recent_errors = list(self.history['errors'])[-10:]
            if len(recent_errors) > 1:
                error_rate = recent_errors[-1] - recent_errors[0]
                if error_rate > self.alerts['error_rate_high']:
                    self.active_alerts.append(f"HIGH ERROR RATE: {error_rate} errors/sample")
                    
    def draw_header(self, stdscr, y, x, width):
        """Draw header section"""
        title = "IPFIX Enricher Monitor"
        subtitle = f"Monitoring: {self.log_file}"
        
        # Title
        stdscr.attron(self.colors['header'] | curses.A_BOLD)
        stdscr.addstr(y, x + (width - len(title)) // 2, title)
        stdscr.attroff(self.colors['header'] | curses.A_BOLD)
        
        # Subtitle
        stdscr.attron(self.colors['info'])
        stdscr.addstr(y + 1, x + (width - len(subtitle)) // 2, subtitle)
        stdscr.attroff(self.colors['info'])
        
        # Separator
        stdscr.addstr(y + 2, x, "-" * width)
        
        return y + 3
        
    def draw_alerts(self, stdscr, y, x, width):
        """Draw alerts section"""
        if self.active_alerts:
            stdscr.attron(self.colors['error'] | curses.A_BOLD | curses.A_BLINK)
            stdscr.addstr(y, x, "! ALERTS:")
            stdscr.attroff(self.colors['error'] | curses.A_BOLD | curses.A_BLINK)
            
            for i, alert in enumerate(self.active_alerts[:3]):
                stdscr.attron(self.colors['error'])
                stdscr.addstr(y + i + 1, x + 2, f"* {alert}")
                stdscr.attroff(self.colors['error'])
                
            return y + len(self.active_alerts) + 2
        return y
        
    def draw_stats(self, stdscr, y, x, width):
        """Draw main statistics"""
        stats = self.current_stats
        
        # Column layout
        col1_x = x
        col2_x = x + width // 2
        
        def draw_stat(y, label, value, color='normal', col=1):
            stat_x = col1_x if col == 1 else col2_x
            stdscr.attron(self.colors['info'])
            stdscr.addstr(y, stat_x, f"{label}:")
            stdscr.attroff(self.colors['info'])
            stdscr.attron(self.colors[color])
            stdscr.addstr(y, stat_x + len(label) + 2, str(value))
            stdscr.attroff(self.colors[color])
            
        # Processing stats
        stdscr.attron(self.colors['header'] | curses.A_BOLD)
        stdscr.addstr(y, x, "PROCESSING")
        stdscr.attroff(self.colors['header'] | curses.A_BOLD)
        y += 1
        
        uptime = stats.get('uptime', 0)
        uptime_str = f"{uptime//3600}h {(uptime%3600)//60}m {uptime%60}s"
        draw_stat(y, "Uptime", uptime_str, 'info', 1)
        draw_stat(y, "MTU", f"{stats.get('mtu', 0)} bytes", 'info', 2)
        y += 1
        
        processed = stats.get('processed', 0)
        draw_stat(y, "Processed", f"{processed:,} packets", 'normal', 1)
        draw_stat(y, "Rate In", f"{stats.get('pps_in', 0):.1f} pps / {stats.get('mbps_in', 0):.2f} Mbps", 'normal', 2)
        y += 1
        
        # Enrichment stats
        enrichment_rate = stats.get('enrichment_rate', 0)
        enrichment_color = 'good' if enrichment_rate > 95 else 'warning' if enrichment_rate > 80 else 'error'
        draw_stat(y, "Enriched", f"{stats.get('enriched', 0):,} ({enrichment_rate:.1f}%)", enrichment_color, 1)
        draw_stat(y, "Pattern Match", f"{stats.get('match_rate', 0):.1f}%", enrichment_color, 2)
        y += 2
        
        # Forwarding stats
        stdscr.attron(self.colors['header'] | curses.A_BOLD)
        stdscr.addstr(y, x, "FORWARDING")
        stdscr.attroff(self.colors['header'] | curses.A_BOLD)
        y += 1
        
        success_rate = stats.get('success_rate', 0)
        success_color = 'good' if success_rate > 90 else 'warning' if success_rate > 70 else 'error'
        draw_stat(y, "Sent", f"{stats.get('sent', 0):,} ({success_rate:.1f}%)", success_color, 1)
        draw_stat(y, "Rate Out", f"{stats.get('pps_out', 0):.1f} pps / {stats.get('mbps_out', 0):.2f} Mbps", 'normal', 2)
        y += 1
        
        errors = stats.get('errors', 0)
        error_color = 'good' if errors == 0 else 'warning' if errors < 100 else 'error'
        draw_stat(y, "Errors", f"{errors:,}", error_color, 1)
        draw_stat(y, "Dropped", f"{stats.get('buffer_dropped', 0):,}", error_color, 2)
        y += 2
        
        # Buffer stats
        stdscr.attron(self.colors['header'] | curses.A_BOLD)
        stdscr.addstr(y, x, "BUFFER & MEMORY")
        stdscr.attroff(self.colors['header'] | curses.A_BOLD)
        y += 1
        
        buffer_current = stats.get('buffer_current', 0)
        buffer_color = 'good' if buffer_current < 1000 else 'warning' if buffer_current < 5000 else 'error'
        draw_stat(y, "Buffer Size", f"{buffer_current:,} / {stats.get('buffer_peak', 0):,} peak", buffer_color, 1)
        draw_stat(y, "Memory", f"{stats.get('memory', 0):.1f} MB", 'info', 2)
        
        return y + 2
        
    def draw_graph(self, stdscr, y, x, width, height, data, label, unit='', color='normal'):
        """Draw ASCII graph"""
        if not data or len(data) < 2:
            return y + height
            
        # Title
        stdscr.attron(self.colors['info'])
        stdscr.addstr(y, x, f"{label}:")
        stdscr.attroff(self.colors['info'])
        
        # Calculate scale
        data_list = list(data)
        max_val = max(data_list) if data_list else 1
        min_val = min(data_list) if data_list else 0
        
        if max_val == min_val:
            max_val = min_val + 1
            
        # Draw graph
        graph_height = height - 2
        graph_width = width - 10  # Leave space for scale
        
        for i in range(graph_height):
            y_pos = y + 1 + i
            
            # Y-axis label
            y_val = max_val - (max_val - min_val) * i / (graph_height - 1)
            stdscr.addstr(y_pos, x, f"{y_val:6.1f}")
            
            # Graph line
            for j in range(min(len(data_list), graph_width)):
                data_idx = len(data_list) - graph_width + j
                if data_idx >= 0:
                    val = data_list[data_idx]
                    normalized = (val - min_val) / (max_val - min_val)
                    
                    if (graph_height - 1 - i) <= normalized * (graph_height - 1):
                        stdscr.attron(self.colors[color])
                        stdscr.addstr(y_pos, x + 8 + j, "#")
                        stdscr.attroff(self.colors[color])
                    else:
                        stdscr.addstr(y_pos, x + 8 + j, ".")
                        
        # X-axis
        stdscr.addstr(y + height - 1, x + 8, "L" + "-" * (graph_width - 1))
        
        # Current value
        if data_list:
            current = data_list[-1]
            current_str = f"Current: {current:.1f}{unit}"
            stdscr.attron(self.colors[color] | curses.A_BOLD)
            stdscr.addstr(y, x + width - len(current_str) - 1, current_str)
            stdscr.attroff(self.colors[color] | curses.A_BOLD)
            
        return y + height
        
    def draw_help(self, stdscr, y, x, width):
        """Draw help section"""
        help_text = "q: Quit | r: Reset | F5: Refresh"
        stdscr.attron(self.colors['info'])
        stdscr.addstr(y, x + (width - len(help_text)) // 2, help_text)
        stdscr.attroff(self.colors['info'])
        
    def run(self, stdscr):
        """Main UI loop"""
        # Setup
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        stdscr.timeout(1000)  # Refresh every second
        
        self.init_colors()
        
        while self.running:
            try:
                # Read latest stats
                self.read_latest_stats()
                self.check_alerts()
                
                # Clear screen
                stdscr.clear()
                
                # Get dimensions
                height, width = stdscr.getmaxyx()
                
                # Draw sections
                y = 0
                y = self.draw_header(stdscr, y, 0, width)
                y = self.draw_alerts(stdscr, y, 0, width)
                y = self.draw_stats(stdscr, y, 0, width)
                
                # Draw graphs if space available
                if height - y > 20:
                    y += 1
                    stdscr.attron(self.colors['header'] | curses.A_BOLD)
                    stdscr.addstr(y, 0, "PERFORMANCE GRAPHS")
                    stdscr.attroff(self.colors['header'] | curses.A_BOLD)
                    y += 1
                    
                    graph_height = 6
                    half_width = width // 2 - 1
                    
                    # Success rate graph
                    success_color = 'good' if self.current_stats.get('success_rate', 0) > 90 else 'warning'
                    self.draw_graph(stdscr, y, 0, half_width, graph_height, 
                                  self.history['success_rate'], "Success Rate", "%", success_color)
                    
                    # PPS graph
                    self.draw_graph(stdscr, y, half_width + 1, half_width, graph_height,
                                  self.history['pps_out'], "Packets/sec Out", " pps", 'info')
                    
                    y += graph_height + 1
                    
                    # Buffer graph
                    buffer_color = 'good' if self.current_stats.get('buffer_current', 0) < 1000 else 'warning'
                    self.draw_graph(stdscr, y, 0, half_width, graph_height,
                                  self.history['buffer_size'], "Buffer Size", "", buffer_color)
                    
                    # Enrichment rate graph
                    self.draw_graph(stdscr, y, half_width + 1, half_width, graph_height,
                                  self.history['enrichment_rate'], "Enrichment Rate", "%", 'good')
                    
                # Help at bottom
                self.draw_help(stdscr, height - 1, 0, width)
                
                # Refresh
                stdscr.refresh()
                
                # Handle input
                key = stdscr.getch()
                if key == ord('q'):
                    self.running = False
                elif key == ord('r'):
                    # Reset history
                    for hist in self.history.values():
                        hist.clear()
                elif key == curses.KEY_F5:
                    # Force refresh
                    pass
                    
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                # Continue on errors
                pass
                
def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='IPFIX Enricher Monitor')
    parser.add_argument('-l', '--log-file', 
                       default='/var/log/ipfix-enricher/ipfix-enricher.log',
                       help='Path to log file')
    parser.add_argument('-r', '--refresh-rate', 
                       type=int, default=1,
                       help='Refresh rate in seconds')
    args = parser.parse_args()
    
    # Check if log file exists
    if not os.path.exists(args.log_file):
        print(f"Error: Log file not found: {args.log_file}")
        sys.exit(1)
        
    # Check if running as root
    if os.geteuid() != 0:
        print("Warning: Not running as root, may not be able to read log file")
        
    # Create monitor
    monitor = IPFIXMonitor(args.log_file)
    
    # Setup signal handler
    def signal_handler(sig, frame):
        monitor.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run UI
    try:
        curses.wrapper(monitor.run)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    print("\nMonitor stopped.")

if __name__ == '__main__':
    main()
