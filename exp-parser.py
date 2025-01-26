import plistlib
import binascii
from collections import defaultdict
import struct
from datetime import datetime, timedelta
import re
from typing import Dict, List, Any
import csv

def parse_wns_time(data: bytes, start_idx: int) -> datetime:
    """Parse WNS.time format timestamp from binary data."""
    try:
        # Skip the WNS.time# prefix
        start_idx = start_idx + 9
        
        # Read 8 bytes after the prefix
        timestamp_bytes = data[start_idx:start_idx + 8]
        if len(timestamp_bytes) == 8:
            # WNS uses double-precision floating point for seconds since epoch
            timestamp = struct.unpack('>d', timestamp_bytes)[0]
            
            # WNS uses 2001-01-01 as epoch base (like Apple)
            base_date = datetime(2001, 1, 1)
            
            # Convert to UTC datetime
            dt = base_date + timedelta(seconds=timestamp)
            
            # Debug timestamp conversion
            print(f"Raw timestamp value: {timestamp}")
            print(f"Converted datetime: {dt}")
            
            return dt
    except Exception as e:
        print(f"Error parsing timestamp: {e}")
    return None

def parse_field_length(data: bytes, start_idx: int) -> tuple[int, int]:
    """Parse field length marker and return tuple of (length, bytes_consumed)."""
    if data[start_idx] == 0x10:  # Single byte length marker
        return data[start_idx + 1], 2
    elif data[start_idx] == 0x11:  # Two byte length marker
        length = (data[start_idx + 1] << 8) | data[start_idx + 2]
        return length, 3
    return 0, 0

def parse_call_properties(data: bytes) -> Dict[str, Any]:
    properties = {}
    
    # Enhanced call direction parsing
    # Look for specific byte patterns that indicate call direction
    direction_patterns = [
        (b'outgoing', b'\x10\x01', 'outgoing'),  # Pattern for outgoing calls
        (b'incoming', b'\x10\x02', 'incoming'),   # Pattern for incoming calls
        (b'missed', b'\x10\x03', 'missed'),       # Pattern for missed calls
        (b'rejected', b'\x10\x04', 'rejected'),   # Pattern for rejected calls
        (b'blocked', b'\x10\x05', 'blocked')      # Pattern for blocked calls
    ]
    
    for pattern_name, pattern_bytes, direction_type in direction_patterns:
        # Search for the pattern name first
        pattern_pos = data.find(pattern_name)
        if pattern_pos != -1:
            # Look for the corresponding byte pattern within a reasonable range
            direction_pos = data.find(pattern_bytes, pattern_pos, pattern_pos + 20)
            if direction_pos != -1:
                properties['direction'] = direction_type
                print(f"Found {direction_type} call at position {direction_pos}")
                break
    
    # Enhanced duration parsing with field length handling
    duration_pos = data.find(b'duration')
    if duration_pos != -1:
        # Skip 'duration' text and look for length marker
        pos = duration_pos + 8  # len('duration')
        if pos < len(data):
            length, bytes_consumed = parse_field_length(data, pos)
            if length > 0 and length < 86400:  # Sanity check: duration less than 24 hours
                try:
                    duration_bytes = data[pos + bytes_consumed:pos + bytes_consumed + length]
                    duration_str = duration_bytes.decode('ascii')
                    properties['duration'] = int(duration_str)
                    print(f"Parsed duration: {properties['duration']} seconds")
                except (ValueError, UnicodeDecodeError) as e:
                    print(f"Error parsing duration: {e}")
    
    # Parse other properties with explicit length handling
    for field_name in [b'callType', b'service', b'callerIdLocation']:
        field_pos = data.find(field_name)
        if field_pos != -1:
            pos = field_pos + len(field_name)
            if pos < len(data):
                length, bytes_consumed = parse_field_length(data, pos)
                if length > 0:
                    try:
                        field_bytes = data[pos + bytes_consumed:pos + bytes_consumed + length]
                        field_value = field_bytes.decode('utf-8')
                        properties[field_name.decode('ascii')] = field_value
                        print(f"Parsed {field_name}: {field_value}")
                    except (ValueError, UnicodeDecodeError) as e:
                        print(f"Error parsing {field_name}: {e}")
    
    return properties

def standardize_phone_number(number: str) -> str:
    """Standardize phone number to +XXXXXXXXXX format"""
    if not number or number == 'Unknown':
        return 'Unknown'
    
    # Strip all non-digit characters
    digits = ''.join(filter(str.isdigit, number))
    
    # Add + prefix if not present
    if not digits.startswith('+'):
        return f"+{digits}"
    return digits

def extract_call_metadata(data: bytes) -> Dict[str, Any]:
    metadata = {
        'calls': [],
        'stats': defaultdict(int)
    }
    
    # Track seen call IDs to prevent duplicates
    seen_calls = set()
    
    def find_transactions(data: bytes) -> List[bytes]:
        # More precise boundary detection
        transactions = list(re.finditer(b'bplist00.*?(?=bplist00|$)', data, re.DOTALL))
        print(f"\nFound {len(transactions)} potential transactions")
        
        # Debug first transaction if any exist
        if transactions:
            first_trans = transactions[0].group(0)
            print(f"First transaction size: {len(first_trans)} bytes")
            print(f"First transaction hex preview: {binascii.hexlify(first_trans[:50]).decode('ascii')}")
        
        return transactions
    
    # Get the transactions by calling the function
    transactions = find_transactions(data)
    
    for transaction in transactions:
        try:
            transaction_data = transaction.group(0)
            
            # Extract UUID first to check for duplicates
            uuid_match = re.search(rb'\$([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})', transaction_data)
            if not uuid_match:
                continue
                
            call_id = uuid_match.group(1).decode('utf-8')
            if call_id in seen_calls:
                continue
            seen_calls.add(call_id)
            
            call = {
                'id': call_id,
                'number': None,
                'name': None,
                'timestamp': None,
                'duration': None,
                'type': None,
                'direction': None,
                'junk_confidence': None,
                'service': None
            }
            
            # Extract phone number with multiple patterns while preserving original format
            phone_patterns = [
                rb'(?:\\\\|\+)\+?(\d{10,})',  # Pattern for +1 format with escape chars
                rb'\+(\d{10,})',  # Pattern for +1 format without escape
                rb'(?<=[^0-9])(\d{10})(?=[^0-9])',  # Raw 10-digit numbers
                rb'(?<=[^0-9])(\d{3}[-\.\s]\d{3}[-\.\s]\d{4})(?=[^0-9])',  # Format: XXX-XXX-XXXX or XXX.XXX.XXXX
                rb'(?<=[^0-9])\((\d{3})\)\s*\d{3}[-\.\s]\d{4}(?=[^0-9])',  # Format: (XXX) XXX-XXXX
                rb'(?<=[^0-9])(\d{3})\s+\d{3}\s+\d{4}(?=[^0-9])'  # Format: XXX XXX XXXX
            ]
            
            for pattern in phone_patterns:
                phone_match = re.search(pattern, transaction_data)
                if phone_match:
                    try:
                        # Get the matched number and standardize it
                        number = phone_match.group(0).decode('utf-8')
                        number = number.replace('\\', '')
                        call['number'] = standardize_phone_number(number)
                        break
                    except:
                        continue
            
            # Extract contact name (filter out VNSUUID)
            name_match = re.search(rb'_([A-Z][A-Za-z\s]{2,}[A-Z])(?=\s|$)', transaction_data)
            if name_match:
                try:
                    name = name_match.group(1).decode('utf-8')
                    if name != "VNSUUID" and len(name) > 3 and not name.startswith('WNS'):
                        call['name'] = name
                except:
                    pass
            
            # Extract service type and call type
            if b'com.apple.Telephony' in transaction_data:
                call['type'] = 'cellular'
                call['service'] = 'com.apple.Telephony'
                metadata['stats']['cellular'] += 1
            elif b'com.apple.FaceTime' in transaction_data:
                call['type'] = 'facetime'
                call['service'] = 'com.apple.FaceTime'
                metadata['stats']['facetime'] += 1
            
            # Parse call properties with enhanced parsing
            properties = parse_call_properties(transaction_data)
            call.update(properties)
            
            # Update stats based on direction
            if call['direction'] in metadata['stats']:
                metadata['stats'][call['direction']] += 1
            
            # Extract timestamp
            time_idx = transaction_data.find(b'WNS.time#')
            if time_idx != -1:
                call['timestamp'] = parse_wns_time(transaction_data, time_idx)
            
            # Extract junk confidence (improved pattern)
            junk_match = re.search(rb'junkConfidence\D*(\d{1,3})(?!\d)', transaction_data)
            if junk_match:
                try:
                    confidence = int(junk_match.group(1))
                    if 0 <= confidence <= 100:  # Valid percentage range
                        call['junk_confidence'] = confidence
                except:
                    pass
            
            metadata['calls'].append(call)
            
        except Exception as e:
            print(f"Error parsing call record: {e}")
    
    return metadata

def adjust_timestamp(ts: datetime) -> datetime:
    """Adjust timestamp by subtracting 5 hours for local timezone"""
    if ts:
        # First handle year adjustment if needed
        if ts.year > 2024:
            ts = ts.replace(year=ts.year - 115)
        # Then subtract 5 hours for timezone
        return ts - timedelta(hours=5)
    return ts

def export_to_csv(calls: List[Dict], filename: str = 'call_history.csv'):
    """Export call records to CSV file with enhanced formatting and statistics"""
    # Track date ranges per number
    number_dates = defaultdict(lambda: {
        'first': None, 
        'last': None, 
        'count': 0
    })
    
    # Process calls to get date ranges and call details
    for call in calls:
        number = call['number'] if call['number'] else 'Unknown'
        if call['timestamp']:
            adjusted_ts = adjust_timestamp(call['timestamp'])
            if (number_dates[number]['first'] is None or 
                adjusted_ts < number_dates[number]['first']):
                number_dates[number]['first'] = adjusted_ts
            if (number_dates[number]['last'] is None or 
                adjusted_ts > number_dates[number]['last']):
                number_dates[number]['last'] = adjusted_ts
            number_dates[number]['count'] += 1
    
    # Define CSV headers in specified order
    headers = [
        'Phone Number',
        'Call Timestamp',
        'First Call',
        'Last Call',
        'Call Count',
        'Call Type',
        'Service'
    ]
    
    try:
        # Pre-process calls for statistics
        number_stats = defaultdict(lambda: {
            'count': 0,
            'types': defaultdict(int)
        })
        
        for call in calls:
            number = call['number'] if call['number'] else 'Unknown'
            number_stats[number]['count'] += 1
            if call['type']:
                number_stats[number]['types'][call['type']] += 1

        # Sort calls by adjusted timestamp
        sorted_calls = sorted(calls, key=lambda x: adjust_timestamp(x['timestamp']) if x['timestamp'] else datetime.min)
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            for call in sorted_calls:
                number = call['number'] if call['number'] else 'Unknown'
                
                # Format phone number with + prefix
                formatted_number = standardize_phone_number(number)

                # Format timestamps
                current_timestamp = ''
                if call['timestamp']:
                    adjusted_ts = adjust_timestamp(call['timestamp'])
                    current_timestamp = adjusted_ts.strftime('%Y-%m-%d %H:%M:%S')

                writer.writerow({
                    'Phone Number': formatted_number,
                    'Call Timestamp': current_timestamp,
                    'First Call': number_dates[number]['first'].strftime('%Y-%m-%d %H:%M:%S') if number_dates[number]['first'] else '',
                    'Last Call': number_dates[number]['last'].strftime('%Y-%m-%d %H:%M:%S') if number_dates[number]['last'] else '',
                    'Call Count': number_stats[number]['count'],
                    'Call Type': call['type'] if call['type'] else '',
                    'Service': call['service'] if call['service'] else ''
                })

        print(f"\nExported {len(calls)} records to {filename}")
        
    except Exception as e:
        print(f"Error exporting to CSV: {e}")

def analyze_plists(data: bytes):
    """Analyze binary plists in the data"""
    # Find all bplist markers
    bplist_positions = [i for i in range(len(data)) if data[i:i+8] == b'bplist00']
    
    print(f"\nBinary Plist Analysis:")
    print(f"Total bplist markers found: {len(bplist_positions)}")
    
    if bplist_positions:
        print("\nFirst 5 bplist positions:", bplist_positions[:5])
        
        # Analyze gaps between plists
        gaps = [bplist_positions[i+1] - bplist_positions[i] 
                for i in range(len(bplist_positions)-1)]
        if gaps:
            print(f"\nAverage gap between plists: {sum(gaps)/len(gaps):.0f} bytes")
            print(f"Smallest gap: {min(gaps)} bytes")
            print(f"Largest gap: {max(gaps)} bytes")
        
        # Analyze first few plists
        for i, pos in enumerate(bplist_positions[:3]):
            # Get next position or end of file
            next_pos = bplist_positions[i+1] if i+1 < len(bplist_positions) else len(data)
            plist_size = next_pos - pos
            print(f"\nPlist #{i+1} at position {pos}:")
            print(f"Size: {plist_size} bytes")
            print(f"Header: {data[pos:pos+20].hex()}")

def main():
    # Open and convert the log file to hex
    with open('1F4D44A7-1B7A-4EB8-8B91-48C01F4F4573.log', 'rb') as f:
        raw_data = f.read()
        print(f"\nRaw data size: {len(raw_data)} bytes")
        
        hex_data = binascii.hexlify(raw_data)
        print(f"Hex data size: {len(hex_data)} bytes")
        
        # Convert back to bytes for processing
        processed_data = binascii.unhexlify(hex_data)
        
        # Analyze binary plists
        analyze_plists(processed_data)
        
    print("\nAnalyzing Call History Records:")
    metadata = extract_call_metadata(processed_data)
    
    # Print summary statistics
    total_calls = len(metadata['calls'])
    print(f"\nTotal Calls Found: {total_calls}")
    print("\nCall Statistics:")
    for stat, count in metadata['stats'].items():
        print(f"  {stat.title()}: {count}")
    
    # Sort calls by timestamp in descending order (most recent first)
    sorted_calls = sorted(metadata['calls'], 
                         key=lambda x: adjust_timestamp(x['timestamp']) if x['timestamp'] else datetime.min,
                         reverse=True)
    
    # Print earliest and latest timestamps
    if sorted_calls:
        latest = adjust_timestamp(sorted_calls[0]['timestamp'])
        earliest = adjust_timestamp(sorted_calls[-1]['timestamp'])
        print(f"\nDate Range: {earliest.strftime('%Y-%m-%d %H:%M:%S')} to {latest.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Print all call records
    print("\nCall Records (Most Recent First):")
    print("-" * 80)
    for call in sorted_calls:
        print(f"\nCall ID: {call['id']}")
        print(f"Number: {call['number']}")
        if call['name']:
            print(f"Name: {call['name']}")
        if call['timestamp']:
            # Format timestamp as YYYY-MM-DD HH:MM:SS with timezone adjustment
            adjusted_ts = adjust_timestamp(call['timestamp'])
            print(f"Time: {adjusted_ts.strftime('%Y-%m-%d %H:%M:%S')}")
        if call['duration']:
            # Convert duration to HH:MM:SS format
            duration_secs = int(call['duration'])
            hours = duration_secs // 3600
            minutes = (duration_secs % 3600) // 60
            seconds = duration_secs % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            print(f"Duration: {duration_str}")
        print(f"Type: {call['type']}")
        print(f"Direction: {call['direction']}")
        if call['junk_confidence'] is not None:
            print(f"Junk Confidence: {call['junk_confidence']}%")
        if call['service']:
            print(f"Service: {call['service']}")
    
    # Export to CSV
    export_to_csv(metadata['calls'])

if __name__ == '__main__':
    main()
