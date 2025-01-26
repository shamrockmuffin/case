import re
import struct
import binascii
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict
import sys

def parse_wns_time(data: bytes, start_idx: int) -> Optional[datetime]:
    try:
        # Skip 'WNS.time#' prefix (9 bytes) and read 8 bytes for the timestamp
        timestamp_bytes = data[start_idx + 9:start_idx + 17]
        timestamp_value = struct.unpack('>d', timestamp_bytes)[0]
        
        # Convert to datetime (reference date is January 1, 2001)
        reference_date = datetime(2001, 1, 1)
        return reference_date + timedelta(seconds=timestamp_value)
    except Exception as e:
        print(f"Error parsing timestamp: {e}")
        return None

def parse_call_record(transaction_data: bytes) -> Dict[str, Any]:
    record = {}
    
    # Extract timestamp
    time_idx = transaction_data.find(b'WNS.time#')
    if time_idx != -1:
        timestamp = parse_wns_time(transaction_data, time_idx)
        if timestamp:
            record['date'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    # Extract participant UUID and direction
    if b'outgoingLocalParticipantUUID' in transaction_data:
        record['direction'] = 'outgoing'
        uuid_start = transaction_data.find(b'outgoingLocalParticipantUUID') + len(b'outgoingLocalParticipantUUID')
    elif b'incomingLocalParticipantUUID' in transaction_data:
        record['direction'] = 'incoming'
        uuid_start = transaction_data.find(b'incomingLocalParticipantUUID') + len(b'incomingLocalParticipantUUID')
    
    # Extract phone number (improved pattern)
    phone_patterns = [
        rb'\\+\d{10,}',  # International format with escape
        rb'\+\d{10,}',   # International format
        rb'\\d{10,}',    # Local format with escape
        rb'\d{10,}'      # Local format
    ]
    
    for pattern in phone_patterns:
        phone_match = re.search(pattern, transaction_data)
        if phone_match:
            phone = phone_match.group(0).decode('utf-8').replace('\\', '')
            record['phone'] = phone
            break
    
    # Extract service type
    if b'com.apple.FaceTime' in transaction_data:
        record['serviceType'] = 'com.apple.FaceTime'
    else:
        record['serviceType'] = 'com.apple.Telephony'
    
    # Extract duration using multiple patterns
    duration_patterns = [
        rb'zduration";\s*=\s*([0-9.]+(?:e[+-]?\d+)?)',  # Database style duration with scientific notation
        rb'duration";\s*=\s*([0-9.]+(?:e[+-]?\d+)?)',   # Standard duration with scientific notation
        rb'#@([0-9.]+(?:e[+-]?\d+)?)',                  # Scientific notation
        rb'DURATION.*?([0-9.]+(?:e[+-]?\d+)?)'          # Generic DURATION field
    ]
    
    for pattern in duration_patterns:
        duration_match = re.search(pattern, transaction_data)
        if duration_match:
            try:
                duration_str = duration_match.group(1).decode('utf-8')
                duration = float(duration_str)
                if 0 <= duration < 3600:  # Allow durations up to 1 hour
                    record['duration'] = duration  # Store exact value without rounding
                    break
            except (ValueError, TypeError, AttributeError):
                continue
    
    # If no duration found but call was answered, set duration to 0
    if 'duration' not in record and b'answered' in transaction_data:
        record['duration'] = 0
    
    return record

def find_bplist_boundaries(data: bytes) -> List[tuple]:
    boundaries = []
    pos = 0
    while True:
        start = data.find(b'bplist00', pos)
        if start == -1:
            break
        end = data.find(b'bplist00', start + 8)
        if end == -1:
            boundaries.append((start, len(data)))
            break
        boundaries.append((start, end))
        pos = end
    return boundaries

def parse_call_log(log_file: str) -> List[Dict[str, Any]]:
    try:
        with open(log_file, 'rb') as f:
            data = f.read()
        
        records = []
        boundaries = find_bplist_boundaries(data)
        
        for start, end in boundaries:
            transaction_data = data[start:end]
            record = parse_call_record(transaction_data)
            if record and 'date' in record:  # Only include records with valid timestamps
                records.append(record)
        
        # Sort records by date
        records.sort(key=lambda x: x.get('date', ''))
        return records
    
    except Exception as e:
        print(f"Error parsing call log: {e}")
        return []

def analyze_durations(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    stats = {
        'total_calls': len(records),
        'calls_with_duration': 0,
        'total_duration': 0,
        'min_duration': float('inf'),
        'max_duration': 0,
        'duration_distribution': defaultdict(int),
        'service_type_durations': defaultdict(list),
        'zero_duration_calls': 0
    }
    
    for record in records:
        if 'duration' in record:
            duration = record['duration']
            stats['calls_with_duration'] += 1
            stats['total_duration'] += duration
            
            if duration == 0:
                stats['zero_duration_calls'] += 1
            else:
                stats['min_duration'] = min(stats['min_duration'], duration)
                stats['max_duration'] = max(stats['max_duration'], duration)
            
            # Categorize durations
            if duration == 0:
                category = '0s (unanswered)'
            elif duration < 5:
                category = '1-4s'
            elif duration < 10:
                category = '5-9s'
            elif duration < 30:
                category = '10-29s'
            elif duration < 60:
                category = '30-59s'
            else:
                category = '60s+'
            
            stats['duration_distribution'][category] += 1
            
            # Track durations by service type
            service_type = record.get('serviceType', 'Unknown')
            stats['service_type_durations'][service_type].append(duration)
    
    # Calculate averages for each service type
    stats['service_type_avg_duration'] = {}
    for service_type, durations in stats['service_type_durations'].items():
        if durations:
            avg_duration = sum(durations) / len(durations)
            stats['service_type_avg_duration'][service_type] = round(avg_duration, 2)
    
    # If no calls with duration, set min_duration to 0
    if stats['min_duration'] == float('inf'):
        stats['min_duration'] = 0
    
    return stats

def decode_value(data, offset, marker):
    try:
        # Handle different binary plist value types
        if marker == 0x10:  # Int
            return struct.unpack('>B', data[offset:offset+1])[0]
        elif marker == 0x11:  # Int
            return struct.unpack('>H', data[offset:offset+2])[0]
        elif marker == 0x12:  # Int
            return struct.unpack('>I', data[offset:offset+4])[0]
        elif marker == 0x13:  # Int
            return struct.unpack('>Q', data[offset:offset+8])[0]
        elif marker == 0x20:  # Real
            return struct.unpack('>f', data[offset:offset+4])[0]
        elif marker == 0x21:  # Real
            return struct.unpack('>d', data[offset:offset+8])[0]
    except struct.error:
        return None
    return None

def find_pattern(data, pattern):
    unique_values = set()
    offset = 0
    while True:
        offset = data.find(pattern.encode(), offset)
        if offset == -1:
            break
            
        print(f"\nFound '{pattern}' at offset {offset}")
        
        # Look at a larger context around the pattern
        context_start = max(0, offset - 32)
        context_end = min(len(data), offset + 64)
        context_bytes = data[context_start:context_end]
        print(f"Context bytes: {' '.join(f'{b:02x}' for b in context_bytes)}")
        print(f"ASCII: {' '.join(chr(b) if 32 <= b <= 126 else '.' for b in context_bytes)}")
        
        # Look for value markers in the context
        for i in range(-32, 64):
            pos = offset + i
            if pos < 0 or pos >= len(data):
                continue
                
            marker = data[pos]
            if marker in [0x10, 0x11, 0x12, 0x13, 0x20, 0x21]:  # Known value markers
                value = decode_value(data, pos + 1, marker)
                if value is not None:
                    print(f"\nFound value marker 0x{marker:02x} at offset {pos}")
                    value_length = 1 if marker == 0x10 else 2 if marker == 0x11 else 4 if marker in [0x12, 0x20] else 8
                    value_bytes = data[pos+1:pos+1+value_length]
                    print(f"Value bytes: {' '.join(f'{b:02x}' for b in value_bytes)}")
                    print(f"Decoded value: {value}")
                    
                    if isinstance(value, (int, float)) and value > 0:
                        unique_values.add(value)
                        if value > 1000000000:  # Looks like a timestamp
                            print(f"As timestamp: {datetime.fromtimestamp(value)}")
                        else:  # Might be a duration
                            if isinstance(value, float):
                                hours = int(value // 3600)
                                minutes = int((value % 3600) // 60)
                                seconds = value % 60
                                print(f"As duration: {hours}h {minutes}m {seconds:.3f}s ({value:.3f} seconds)")
                            else:
                                hours = value // 3600
                                minutes = (value % 3600) // 60
                                seconds = value % 60
                                print(f"As duration: {hours}h {minutes}m {seconds}s ({value} seconds)")
        
        offset += 1
    
    if unique_values:
        print("\nUnique values found:")
        values_list = sorted(unique_values)
        for value in values_list:
            if value > 1000000000:  # Timestamp
                print(f"- {value} ({datetime.fromtimestamp(value)})")
            else:  # Duration
                if isinstance(value, float):
                    hours = int(value // 3600)
                    minutes = int((value % 3600) // 60)
                    seconds = value % 60
                    print(f"- {value:.3f} ({hours}h {minutes}m {seconds:.3f}s)")
                else:
                    hours = value // 3600
                    minutes = (value % 3600) // 60
                    seconds = value % 60
                    print(f"- {value} ({hours}h {minutes}m {seconds}s)")
    else:
        print("\nNo valid values were found")

def main():
    try:
        with open('1F4D44A7-1B7A-4EB8-8B91-48C01F4F4573.log', 'rb') as f:
            data = f.read()
            find_pattern(data, 'duration')
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
