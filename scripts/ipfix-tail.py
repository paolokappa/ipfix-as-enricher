#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPFIX Enricher Log Tail
Colored tail for ipfix-enricher logs
"""

import sys
import re
import time
import subprocess
import argparse

class ColoredTail:
    def __init__(self, log_file='/var/log/ipfix-enricher/ipfix-enricher.log'):
        self.log_file = log_file
        
        # Color codes
        self.colors = {
            'ERROR': '\033[31m',
            'WARNING': '\033[33m',
            'CRITICAL': '\033[91m',
            'INFO': '\033[34m',
            'DEBUG': '\033[90m',
            'SUCCESS': '\033[32m',
            'RESET': '\033[0m',
            'BOLD': '\033[1m'
        }
        
    def colorize_line(self, line):
        """Apply colors to log line"""
        # Color log levels
        for level, color in self.colors.items():
            if level in ['ERROR', 'WARNING', 'CRITICAL', 'INFO', 'DEBUG']:
                line = re.sub(f'\\b{level}\\b', f'{color}{level}{self.colors["RESET"]}', line)
                
        # Color success rates
        line = re.sub(r'(\d+\.?\d*)% success', 
                     lambda m: f'{self.colors["SUCCESS"]}{m.group(1)}% success{self.colors["RESET"]}', 
                     line)
                     
        # Color high numbers in errors
        if 'Errors:' in line:
            line = re.sub(r'Errors: (\d+)', 
                         lambda m: f'Errors: {self.colors["ERROR"] if int(m.group(1)) > 0 else self.colors["SUCCESS"]}{m.group(1)}{self.colors["RESET"]}', 
                         line)
                         
        # Highlight statistics header
        if 'Statistics:' in line:
            line = f'{self.colors["BOLD"]}{line}{self.colors["RESET"]}'
            
        return line
        
    def run(self):
        """Run colored tail"""
        try:
            # Use subprocess to tail the file
            tail_process = subprocess.Popen(
                ['tail', '-f', self.log_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            print(f"Tailing {self.log_file} (Ctrl+C to stop)...")
            print("-" * 60)
            
            # Process each line
            for line in tail_process.stdout:
                colored_line = self.colorize_line(line.rstrip())
                print(colored_line)
                
        except KeyboardInterrupt:
            print("\n\nStopping tail...")
            tail_process.terminate()
            
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='Colored tail for IPFIX Enricher logs')
    parser.add_argument('-l', '--log-file',
                       default='/var/log/ipfix-enricher/ipfix-enricher.log',
                       help='Path to log file')
    parser.add_argument('-n', '--lines',
                       type=int,
                       default=10,
                       help='Number of initial lines to show')
    args = parser.parse_args()
    
    # Create and run colored tail
    tail = ColoredTail(args.log_file)
    tail.run()
    
if __name__ == '__main__':
    main()
