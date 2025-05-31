#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPFIX AS Enricher - Production Version 5.1
With proper logging to file
"""

import socket
import struct
import time
import sys
import signal
import os
import gc
import threading
import errno
import select
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from collections import deque

# Setup logging before anything else
def setup_logging():
    """Configure logging with file rotation"""
    # Create log directory
    log_dir = '/var/log/ipfix-enricher'
    os.makedirs(log_dir, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('ipfix-enricher')
    logger.setLevel(logging.DEBUG)
    
    # File handler with rotation (10MB per file, keep 5 files)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'ipfix-enricher.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler - only CRITICAL messages go to journal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.CRITICAL)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logging()

# Log startup
logger.info("="*60)
logger.info("IPFIX AS Enricher v5.1 starting...")
logger.info("="*60)

class CircularBuffer:
    """Thread-safe circular buffer for traffic spikes"""
    def __init__(self, size=10000):
        self.buffer = deque(maxlen=size)
        self.lock = threading.Lock()
        self.dropped = 0
        
    def put(self, item):
        with self.lock:
            if len(self.buffer) >= self.buffer.maxlen:
                self.dropped += 1
                return False
            self.buffer.append(item)
            return True
            
    def get_batch(self, max_items=100):
        items = []
        with self.lock:
            while self.buffer and len(items) < max_items:
                items.append(self.buffer.popleft())
        return items
        
    def size(self):
        with self.lock:
            return len(self.buffer)

class IPFIXEnricher:
    def __init__(self):
        # Configuration
        self.listen_port = 9996
        self.destination = ('185.54.81.20', 9996)
        self.target_as = 202032
        
        # MTU settings
        self.max_packet_size = 1400
        self.mtu_discovery_enabled = False
        self.discovered_mtu = None
        
        # Compiled patterns for fast matching
        self.ipv4_prefixes = [
            struct.pack('BBB', 185, 54, 80),
            struct.pack('BBB', 185, 54, 81),
            struct.pack('BBB', 185, 54, 82),
            struct.pack('BBB', 185, 54, 83),
        ]
        
        self.ipv6_prefix = bytes.fromhex('2a024460')
        
        # AS numbers in network byte order
        self.as_target = struct.pack('!I', self.target_as)
        self.as_zero = struct.pack('!I', 0)
        
        # Buffer for traffic spikes
        self.send_buffer = CircularBuffer(size=20000)
        
        # Thread-safe statistics
        self.stats = {
            'processed': 0,
            'enriched': 0,
            'sent': 0,
            'errors': 0,
            'dropped': 0,
            'oversized': 0,
            'fragmented': 0,
            'ipv4_matched': 0,
            'ipv6_matched': 0,
            'as_zero_found': 0,
            'as_replaced': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'buffer_max': 0,
            'error_types': {},
            'last_packet_time': 0,
            'max_packet_seen': 0,
            'size_distribution': {},
            'debug_packets_shown': 0,
        }
        self.stats_lock = threading.Lock()
        
        # Timing
        self.start_time = time.time()
        self.last_stats_time = time.time()
        self.last_gc_time = time.time()
        self.last_debug_time = time.time()
        
        # Control flags
        self.running = True
        self.sender_thread = None
        self.debug_mode = True
        self.max_debug_packets = 10
        
        # Sockets
        self.recv_sock = None
        self.send_sock = None
        
        # Performance counters
        self.packets_since_stats = 0
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle signals for clean shutdown"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
    def _optimize_system(self):
        """Optimize system settings"""
        optimizations = [
            ('/proc/sys/net/core/wmem_max', '16777216'),
            ('/proc/sys/net/core/rmem_max', '16777216'),
            ('/proc/sys/net/core/wmem_default', '4194304'),
            ('/proc/sys/net/core/rmem_default', '4194304'),
            ('/proc/sys/net/core/netdev_max_backlog', '10000'),
            ('/proc/sys/net/ipv4/udp_mem', '102400 873800 16777216'),
        ]
        
        for path, value in optimizations:
            try:
                with open(path, 'w') as f:
                    f.write(value)
            except Exception as e:
                logger.debug(f"Could not optimize {path}: {e}")
                
        logger.info("System optimizations applied")
        
    def _discover_path_mtu(self):
        """Discover path MTU"""
        logger.info(f"Discovering path MTU to {self.destination[0]}...")
        
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.settimeout(0.5)
        
        test_sizes = [1500, 1400, 1300, 1200]
        best_mtu = 576
        
        for size in test_sizes:
            try:
                test_packet = struct.pack('!HHIII', 10, size, int(time.time()), 0, 0)
                test_packet += b'\x00' * (size - len(test_packet))
                test_sock.sendto(test_packet, self.destination)
                if size > best_mtu:
                    best_mtu = size
                logger.debug(f"MTU {size} bytes: OK")
            except socket.error as e:
                if e.errno == errno.EMSGSIZE:
                    logger.debug(f"MTU {size} bytes: too large")
                else:
                    logger.debug(f"MTU {size} bytes: error {e}")
                    
        test_sock.close()
        
        self.discovered_mtu = best_mtu - 28
        self.max_packet_size = min(self.discovered_mtu, 1400)
        
        logger.info(f"Path MTU discovered: {self.discovered_mtu} bytes")
        logger.info(f"Using max packet size: {self.max_packet_size} bytes")
        
    def _setup_sockets(self):
        """Setup sockets with optimizations"""
        try:
            self._optimize_system()
            
            # Receive socket
            self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Large receive buffer
            for size in [16777216, 8388608, 4194304, 2097152]:
                try:
                    self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, size)
                    break
                except:
                    continue
                    
            self.recv_sock.bind(('0.0.0.0', self.listen_port))
            self.recv_sock.setblocking(False)
            
            # Send socket
            self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Large send buffer
            for size in [16777216, 8388608, 4194304, 2097152]:
                try:
                    self.send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, size)
                    break
                except:
                    continue
                    
            # Try to enable path MTU discovery
            try:
                if hasattr(socket, 'IP_MTU_DISCOVER') and hasattr(socket, 'IP_PMTUDISC_DO'):
                    self.send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MTU_DISCOVER, socket.IP_PMTUDISC_DO)
                    logger.info("Path MTU discovery enabled")
            except:
                pass
                
            logger.info("Sockets configured successfully")
            logger.info(f"Listen on: 0.0.0.0:{self.listen_port}")
            logger.info(f"Forward to: {self.destination[0]}:{self.destination[1]}")
            
            # Discover MTU
            if self.mtu_discovery_enabled:
                self._discover_path_mtu()
                
            return True
            
        except Exception as e:
            logger.critical(f"Socket setup failed: {e}")
            return False
            
    def _cleanup_sockets(self):
        """Clean socket shutdown"""
        for sock in [self.recv_sock, self.send_sock]:
            if sock:
                try:
                    sock.close()
                except:
                    pass
                    
    def _check_patterns(self, data):
        """Check IP patterns with improved detection"""
        if len(data) < 20:
            return False, False
            
        ipv4_found = False
        ipv6_found = False
        
        # Convert to hex for more reliable search
        hex_data = data.hex()
        
        # Check IPv4 patterns using hex
        for i, prefix in enumerate(self.ipv4_prefixes):
            hex_prefix = prefix.hex()
            if hex_prefix in hex_data:
                ipv4_found = True
                if self.debug_mode and self.stats['debug_packets_shown'] < self.max_debug_packets:
                    pos = hex_data.find(hex_prefix) // 2
                    ip_str = f"{prefix[0]}.{prefix[1]}.{prefix[2]}"
                    logger.debug(f"Found IPv4 pattern #{i} ({ip_str}.x) at byte {pos}")
                break
                
        # Check IPv6
        hex_ipv6 = self.ipv6_prefix.hex()
        if hex_ipv6 in hex_data:
            ipv6_found = True
            if self.debug_mode and self.stats['debug_packets_shown'] < self.max_debug_packets:
                pos = hex_data.find(hex_ipv6) // 2
                logger.debug(f"Found IPv6 pattern at byte {pos}")
                
        # Debug AS search if pattern found
        if (ipv4_found or ipv6_found) and self.debug_mode and self.stats['debug_packets_shown'] < self.max_debug_packets:
            as_count = data.count(self.as_zero)
            if as_count > 0:
                logger.debug(f"Found {as_count} occurrences of AS 0 to replace")
                positions = []
                start = 0
                while len(positions) < 5:
                    pos = data.find(self.as_zero, start)
                    if pos == -1:
                        break
                    positions.append(pos)
                    start = pos + 1
                logger.debug(f"AS 0 positions: {positions}")
                with self.stats_lock:
                    self.stats['as_zero_found'] += as_count
            else:
                logger.debug(f"No AS 0 found in packet (searching for {self.as_zero.hex()})")
                logger.debug(f"First 200 bytes: {data[:200].hex()}")
                
            self.stats['debug_packets_shown'] += 1
            
        return ipv4_found, ipv6_found
        
    def _enrich_packet(self, data):
        """AS enrichment with fixes"""
        if len(data) < 20:
            return data, False
            
        # Check patterns
        ipv4_found, ipv6_found = self._check_patterns(data)
        
        if not (ipv4_found or ipv6_found):
            return data, False
            
        # Update statistics
        with self.stats_lock:
            if ipv4_found:
                self.stats['ipv4_matched'] += 1
            if ipv6_found:
                self.stats['ipv6_matched'] += 1
                
        # Replace AS 0 with target AS
        if self.as_zero in data:
            enriched = data.replace(self.as_zero, self.as_target)
            if enriched != data:
                replacements = data.count(self.as_zero)
                with self.stats_lock:
                    self.stats['as_replaced'] += replacements
                    
                if self.debug_mode and self.stats['enriched'] < 5:
                    logger.debug(f"ENRICHED! Replaced {replacements} AS entries from AS0 to AS{self.target_as}")
                    
                return enriched, True
                
        return data, False
        
    def _sender_thread_func(self):
        """Dedicated thread for sending packets"""
        logger.info("Sender thread started")
        
        consecutive_errors = 0
        last_send_time = time.time()
        eperm_logged = False
        
        while self.running:
            try:
                # Get batch of packets from buffer
                packets = self.send_buffer.get_batch(max_items=50)
                
                if not packets:
                    time.sleep(0.001)
                    continue
                    
                # Send packets
                for packet_data in packets:
                    try:
                        # Check packet size
                        if len(packet_data) > self.max_packet_size:
                            with self.stats_lock:
                                self.stats['oversized'] += 1
                                
                            if self.stats['oversized'] == 1:
                                logger.warning(f"Oversized packet: {len(packet_data)} bytes > {self.max_packet_size} MTU")
                                logger.warning("Dropping oversized packets to avoid fragmentation")
                                
                            continue
                            
                        bytes_sent = self.send_sock.sendto(packet_data, self.destination)
                        
                        with self.stats_lock:
                            self.stats['sent'] += 1
                            self.stats['bytes_sent'] += bytes_sent
                            
                        consecutive_errors = 0
                        last_send_time = time.time()
                        
                    except socket.error as e:
                        if e.errno == errno.EMSGSIZE:
                            with self.stats_lock:
                                self.stats['errors'] += 1
                                self.stats['error_types']['EMSGSIZE'] = \
                                    self.stats['error_types'].get('EMSGSIZE', 0) + 1
                                    
                            if self.max_packet_size > 576:
                                old_mtu = self.max_packet_size
                                self.max_packet_size = max(576, int(self.max_packet_size * 0.9))
                                logger.warning(f"Reducing MTU from {old_mtu} to {self.max_packet_size} after EMSGSIZE errors")
                                
                        elif e.errno == errno.EPERM:
                            with self.stats_lock:
                                self.stats['errors'] += 1
                                self.stats['error_types']['EPERM'] = \
                                    self.stats['error_types'].get('EPERM', 0) + 1
                                    
                            if not eperm_logged:
                                logger.error(f"EPERM: Permission denied sending to {self.destination}")
                                logger.error(f"Fix with: iptables -I OUTPUT -p udp -d {self.destination[0]} --dport {self.destination[1]} -j ACCEPT")
                                eperm_logged = True
                                
                        elif e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                            self.send_buffer.put(packet_data)
                            time.sleep(0.001)
                        else:
                            consecutive_errors += 1
                            self._handle_send_error(e)
                            
                            if consecutive_errors > 100:
                                logger.warning("Too many send errors, pausing 1 second")
                                time.sleep(1)
                                consecutive_errors = 0
                                
                    except Exception as e:
                        self._handle_send_error(e)
                        
                # Timeout check
                if time.time() - last_send_time > 30:
                    logger.warning("No packets sent for 30 seconds")
                    last_send_time = time.time()
                    
            except Exception as e:
                logger.error(f"Error in sender thread: {e}")
                time.sleep(0.1)
                
        logger.info("Sender thread terminated")
        
    def _handle_send_error(self, error):
        """Centralized send error handling"""
        with self.stats_lock:
            self.stats['errors'] += 1
            
            if isinstance(error, socket.error):
                error_name = errno.errorcode.get(error.errno, f"errno_{error.errno}")
            else:
                error_name = type(error).__name__
                
            self.stats['error_types'][error_name] = \
                self.stats['error_types'].get(error_name, 0) + 1
                
            if self.stats['errors'] <= 10:
                logger.error(f"Send failed: {error_name} - {error}")
                
    def _print_stats(self):
        """Print detailed statistics to log file"""
        with self.stats_lock:
            stats = self.stats.copy()
            dropped = self.send_buffer.dropped
            buffer_size = self.send_buffer.size()
            
        now = time.time()
        uptime = now - self.start_time
        
        # Calculate rates
        pps_in = stats['processed'] / uptime if uptime > 0 else 0
        pps_out = stats['sent'] / uptime if uptime > 0 else 0
        mbps_in = (stats['bytes_received'] * 8 / 1048576) / uptime if uptime > 0 else 0
        mbps_out = (stats['bytes_sent'] * 8 / 1048576) / uptime if uptime > 0 else 0
        
        # Calculate percentages
        enrich_rate = (stats['enriched'] / stats['processed'] * 100) if stats['processed'] > 0 else 0
        match_rate = ((stats['ipv4_matched'] + stats['ipv6_matched']) / stats['processed'] * 100) if stats['processed'] > 0 else 0
        success_rate = (stats['sent'] / stats['processed'] * 100) if stats['processed'] > 0 else 0
        drop_rate = (dropped / stats['processed'] * 100) if stats['processed'] > 0 else 0
        oversized_rate = (stats['oversized'] / stats['processed'] * 100) if stats['processed'] > 0 else 0
        
        # Build stats message
        stats_msg = [
            f"\n{'='*60}",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Statistics:",
            f"Uptime: {int(uptime)}s | MTU: {self.max_packet_size} bytes",
            f"\nPattern Detection:",
            f"  IPv4 matches: {stats['ipv4_matched']:,} packets",
            f"  IPv6 matches: {stats['ipv6_matched']:,} packets",
            f"  Total match rate: {match_rate:.1f}%"
        ]
        
        if stats['as_zero_found'] > 0:
            stats_msg.extend([
                f"  AS 0 found: {stats['as_zero_found']:,} occurrences",
                f"  AS replaced: {stats['as_replaced']:,} times"
            ])
        
        stats_msg.extend([
            f"\nProcessing:",
            f"  Processed: {stats['processed']:,} packets ({pps_in:.1f} pps, {mbps_in:.2f} Mbps)",
            f"  Enriched: {stats['enriched']:,} ({enrich_rate:.1f}%)",
            f"  Max packet size: {stats.get('max_packet_seen', 0)} bytes",
            f"\nForwarding to {self.destination[0]}:{self.destination[1]}:",
            f"  Sent: {stats['sent']:,} ({success_rate:.1f}% success)",
            f"  Oversized dropped: {stats['oversized']:,} ({oversized_rate:.1f}%)",
            f"  Buffer dropped: {dropped:,} ({drop_rate:.1f}%)",
            f"  Errors: {stats['errors']:,}",
            f"  Rate: {pps_out:.1f} pps, {mbps_out:.2f} Mbps"
        ])
        
        if buffer_size > 0 or stats.get('buffer_max', 0) > 0:
            stats_msg.extend([
                f"\nBuffer:",
                f"  Current size: {buffer_size}",
                f"  Peak size: {stats.get('buffer_max', 0)}"
            ])
        
        if stats['error_types']:
            stats_msg.append("\nError details:")
            for error_type, count in sorted(stats['error_types'].items(), 
                                          key=lambda x: x[1], reverse=True)[:5]:
                stats_msg.append(f"  {error_type}: {count}")
                
        if stats.get('size_distribution') and len(stats['size_distribution']) > 1:
            stats_msg.append("\nPacket size distribution:")
            for size_range, count in sorted(stats['size_distribution'].items())[:5]:
                stats_msg.append(f"  {size_range}: {count}")
                
        stats_msg.append(f"\nMemory: RSS {self._get_memory_usage():.1f} MB")
        stats_msg.append('='*60)
        
        # Log as info
        logger.info('\n'.join(stats_msg))
        
        # Also print one-line summary to console if success rate is critical
        if success_rate < 50 and stats['processed'] > 100:
            logger.critical(f"Low success rate: {success_rate:.1f}% (sent {stats['sent']:,}/{stats['processed']:,})")
        
        # Disable debug after 2 minutes
        if self.debug_mode and uptime > 120:
            self.debug_mode = False
            logger.info(f"Debug mode disabled after {int(uptime)}s")
            
    def _get_memory_usage(self):
        """Get memory usage in MB"""
        try:
            with open('/proc/self/status', 'r') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        return int(line.split()[1]) / 1024
        except:
            pass
        return 0
        
    def run(self):
        """Main processing loop"""
        logger.info("="*60)
        logger.info("IPFIX AS Enricher v5.1")
        logger.info(f"AS Target: {self.target_as}")
        logger.info(f"Prefixes: 185.54.80-83.x, 2a02:4460::/32")
        logger.info(f"Replacement: AS 0 -> AS {self.target_as}")
        logger.info("="*60)
        
        if not self._setup_sockets():
            return False
            
        # Start sender thread
        self.sender_thread = threading.Thread(target=self._sender_thread_func, daemon=True)
        self.sender_thread.start()
        
        logger.info("Service started successfully")
        logger.info(f"Debug mode active for first {self.max_debug_packets} matching packets")
        logger.info("Processing packets...")
        
        # Buffer for batch processing
        batch = []
        batch_start_time = time.time()
        
        try:
            while self.running:
                try:
                    # Use select for efficiency
                    readable, _, _ = select.select([self.recv_sock], [], [], 0.01)
                    
                    if not readable:
                        if batch:
                            self._process_batch(batch)
                            batch = []
                        continue
                        
                    # Receive packets in batch
                    while len(batch) < 100:
                        try:
                            data, addr = self.recv_sock.recvfrom(65535)
                            
                            with self.stats_lock:
                                self.stats['processed'] += 1
                                self.stats['bytes_received'] += len(data)
                                self.stats['last_packet_time'] = time.time()
                                
                                # Track max size
                                if len(data) > self.stats.get('max_packet_seen', 0):
                                    self.stats['max_packet_seen'] = len(data)
                                    
                                # Size distribution
                                size_bucket = f"{(len(data) // 100) * 100}-{((len(data) // 100) + 1) * 100}"
                                self.stats['size_distribution'][size_bucket] = \
                                    self.stats['size_distribution'].get(size_bucket, 0) + 1
                                
                            batch.append(data)
                            self.packets_since_stats += 1
                            
                        except socket.error as e:
                            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                                break
                            else:
                                raise
                                
                    # Process batch if full or timeout
                    if len(batch) >= 50 or (time.time() - batch_start_time) > 0.01:
                        self._process_batch(batch)
                        batch = []
                        batch_start_time = time.time()
                        
                    # Periodic statistics
                    if self.packets_since_stats >= 5000 or \
                       (time.time() - self.last_stats_time) >= 30:
                        self._print_stats()
                        self.packets_since_stats = 0
                        self.last_stats_time = time.time()
                        
                    # Periodic garbage collection
                    if (time.time() - self.last_gc_time) >= 300:
                        gc.collect()
                        self.last_gc_time = time.time()
                        
                except KeyboardInterrupt:
                    break
                    
                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    time.sleep(0.01)
                    
        except Exception as e:
            logger.critical(f"FATAL ERROR: {e}")
            import traceback
            logger.critical(traceback.format_exc())
            
        finally:
            logger.info("Shutting down...")
            self.running = False
            
            # Wait for sender thread
            if self.sender_thread and self.sender_thread.is_alive():
                self.sender_thread.join(timeout=5)
                
            # Final statistics
            self._print_stats()
            
            # Check remaining buffer
            remaining = self.send_buffer.size()
            if remaining > 0:
                logger.warning(f"{remaining} packets in buffer not sent")
                
            self._cleanup_sockets()
            logger.info("Service stopped")
            
        return True
        
    def _process_batch(self, batch):
        """Process a batch of packets"""
        for data in batch:
            # Enrich packet
            enriched_data, was_enriched = self._enrich_packet(data)
            
            if was_enriched:
                with self.stats_lock:
                    self.stats['enriched'] += 1
                    
            # Add to send buffer
            if not self.send_buffer.put(enriched_data):
                with self.stats_lock:
                    self.stats['dropped'] += 1
                    
            # Update peak buffer
            buffer_size = self.send_buffer.size()
            with self.stats_lock:
                if buffer_size > self.stats.get('buffer_max', 0):
                    self.stats['buffer_max'] = buffer_size

def main():
    """Entry point"""
    try:
        # Set process priority
        try:
            os.nice(-10)
        except:
            pass
            
        # Increase file descriptor limits
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))
        except:
            pass
            
        enricher = IPFIXEnricher()
        success = enricher.run()
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.critical(f"Startup failed: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
