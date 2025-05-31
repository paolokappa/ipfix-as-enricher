# Architecture Documentation

## System Architecture

### Core Components

1. **UDP Listener**
   - Binds to port 2055 (configurable)
   - Receives IPFIX/NetFlow packets
   - Non-blocking socket operations
   - Configurable buffer sizes

2. **Protocol Detector**
   - Identifies packet type (IPFIX vs NetFlow v9)
   - Validates packet structure
   - Routes to appropriate parser

3. **AS Extraction Engine**
   - Template-aware NetFlow v9 parsing
   - IPFIX Information Element handling
   - Fallback heuristic extraction
   - AS number validation

4. **Enrichment Processor**
   - Adds extracted AS information
   - Optional GeoIP lookups
   - Optional DNS enrichment
   - Maintains enrichment cache

5. **Forwarder**
   - Sends enriched packets to collectors
   - Supports multiple destinations
   - Handles connection failures
   - Implements retry logic

6. **Statistics Engine**
   - Real-time metric collection
   - AS frequency tracking
   - Performance counters
   - Telnet API server

### Data Flow

```
1. Packet Reception
   +-> UDP Socket (port 2055)
       +-> Packet Queue

2. Processing Pipeline
   +-> Protocol Detection
       +-> NetFlow v9 Parser
       ¦   +-> Template Manager
       ¦       +-> AS Extractor
       +-> IPFIX Parser
           +-> AS Extractor

3. Enrichment
   +-> AS Information
       +-> Cache Lookup
           +-> Enrichment Application

4. Forwarding
   +-> Destination Selection
       +-> UDP Transmission
           +-> Error Handling

5. Statistics
   +-> Metric Updates
       +-> AS Tracking
           +-> API Updates
```

### Threading Model

- **Main Thread**: Service management, signal handling
- **Receiver Thread**: UDP packet reception
- **Worker Threads**: Packet processing (configurable count)
- **Forwarder Thread**: Outbound packet transmission
- **Stats Thread**: Telnet API server
- **Monitor Thread**: Health checking

### Memory Management

- Circular buffer for packet queue
- LRU cache for AS lookups
- Template cache for NetFlow v9
- Bounded queues prevent memory exhaustion

### Performance Optimizations

1. **Zero-copy forwarding** when no enrichment needed
2. **Packet batching** for improved throughput
3. **Cache-friendly data structures**
4. **CPU affinity** for worker threads
5. **Nice level** adjustment for priority

### Fault Tolerance

- Automatic service restart via systemd
- Graceful degradation without enrichment
- Connection retry with exponential backoff
- Packet drop monitoring
- Health check endpoint
