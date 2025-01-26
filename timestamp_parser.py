import struct
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import binascii

@dataclass
class WNSTimestamp:
    """Represents a WNS timestamp with its type and value."""
    marker: str  # L/M/N/O/P
    index: int
    timestamp: datetime
    raw_bytes: bytes
    offset: int  # Position in file

@dataclass
class CallTimeSequence:
    """Represents a complete sequence of timestamps for a call."""
    call_id: str
    setup: Optional[WNSTimestamp] = None      # LWNS
    initiation: Optional[WNSTimestamp] = None # MNWNS
    connection: Optional[WNSTimestamp] = None # NOWNS
    termination: Optional[WNSTimestamp] = None # OPWNS
    cleanup: Optional[WNSTimestamp] = None    # PWNS

    def get_duration(self) -> Optional[float]:
        """Calculate call duration if connection and termination exist."""
        if self.connection and self.termination:
            return (self.termination.timestamp - self.connection.timestamp).total_seconds()
        return None

    def get_setup_time(self) -> Optional[float]:
        """Calculate setup time if initiation and connection exist."""
        if self.initiation and self.connection:
            return (self.connection.timestamp - self.initiation.timestamp).total_seconds()
        return None

def find_plist_boundaries(data: bytes) -> List[Tuple[int, int]]:
    """Find the start and end positions of binary plists in the data."""
    boundaries = []
    start = 0
    while True:
        start = data.find(b'bplist00', start)
        if start == -1:
            break
        # Find the next bplist marker or end of data
        next_start = data.find(b'bplist00', start + 8)
        end = next_start if next_start != -1 else len(data)
        boundaries.append((start, end))
        start = end
    return boundaries

def parse_wns_time_from_plist(plist_data: bytes) -> Optional[Tuple[datetime, str]]:
    """Extract WNS.time value from a binary plist section."""
    try:
        # Look for WNS.time pattern
        wns_pattern = rb'WNS\.time#([\x00-\xff]{8})'
        match = re.search(wns_pattern, plist_data)
        if not match:
            return None
        
        timestamp_bytes = match.group(1)
        timestamp_value = struct.unpack('>d', timestamp_bytes)[0]
        timestamp = datetime(2001, 1, 1) + timedelta(seconds=timestamp_value)
        
        # Try to determine the type (L/M/N/O/P)
        type_pattern = rb'([LMNOP])\d+WNS\.time'
        type_match = re.search(type_pattern, plist_data)
        marker = type_match.group(1).decode('ascii') if type_match else 'U'
        
        return (timestamp, marker)
    except Exception as e:
        print(f"Error parsing WNS.time: {e}")
        return None

def extract_uuid_from_plist(plist_data: bytes) -> Optional[str]:
    """Extract UUID from a binary plist section."""
    try:
        uuid_pattern = rb'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})'
        match = re.search(uuid_pattern, plist_data)
        if match:
            return match.group(1).decode('ascii')
    except Exception as e:
        print(f"Error extracting UUID: {e}")
    return None

def process_plist_section(data: bytes, start: int, end: int) -> Optional[Tuple[str, List[Tuple[datetime, str]]]]:
    """Process a single binary plist section."""
    try:
        section_data = data[start:end]
        
        # Extract UUID
        uuid = extract_uuid_from_plist(section_data)
        if not uuid:
            return None
            
        # Find all WNS.time entries
        timestamps = []
        pos = 0
        while True:
            result = parse_wns_time_from_plist(section_data[pos:])
            if not result:
                break
            timestamps.append(result)
            pos += 1
            
        if timestamps:
            return (uuid, timestamps)
            
    except Exception as e:
        print(f"Error processing plist section: {e}")
    return None

def main():
    print("Reading log file...")
    with open('1F4D44A7-1B7A-4EB8-8B91-48C01F4F4573.log', 'rb') as f:
        data = f.read()
    
    print(f"Read {len(data)} bytes")
    
    # Find all binary plist sections
    print("\nLocating binary plist sections...")
    boundaries = find_plist_boundaries(data)
    print(f"Found {len(boundaries)} binary plist sections")
    
    # Process each section
    call_sequences: Dict[str, List[Tuple[datetime, str]]] = {}
    
    print("\nProcessing sections...")
    for start, end in boundaries:
        result = process_plist_section(data, start, end)
        if result:
            uuid, timestamps = result
            if uuid not in call_sequences:
                call_sequences[uuid] = []
            call_sequences[uuid].extend(timestamps)
    
    print(f"\nFound {len(call_sequences)} call sequences")
    
    # Print detailed analysis
    for uuid, timestamps in call_sequences.items():
        print(f"\nCall ID: {uuid}")
        print("Timestamps:")
        timestamps.sort(key=lambda x: x[0])  # Sort by timestamp
        for ts, marker in timestamps:
            print(f"  {marker}WNS.time: {ts.strftime('%Y-%m-%d %H:%M:%S.%f')}")
        
        # Calculate durations if possible
        if len(timestamps) >= 2:
            duration = (timestamps[-1][0] - timestamps[0][0]).total_seconds()
            print(f"Total span: {duration:.2f} seconds")
        
        print("-" * 80)

if __name__ == '__main__':
    main() 