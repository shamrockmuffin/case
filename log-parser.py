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
            timestamp = struct.unpack('>d', timestamp_bytes)[0]
            base_date = datetime(2001, 1, 1)
            return base_date + timedelta(seconds=timestamp)
    except Exception as e:
        print(f"Error parsing timestamp: {e}")
    return None
def extract_call_metadata(data: bytes) -> Dict[str, Any]:
    metadata = {
        'calls': [],
        'stats': defaultdict(int)
    }
    
    # Track seen call IDs to prevent duplicates
    seen_calls = set()
    
    def find_transactions(data: bytes) -> List[bytes]:
        # More precise boundary detection
        return re.finditer(b'bplist00.*?(?=bplist00|$)', data, re.DOTALL)
    
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
                        # Preserve the exact format found in the log
                        number = phone_match.group(0).decode('utf-8')
                        # Remove any escape characters but keep the format
                        number = number.replace('\\', '')
                        call['number'] = number
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
            
            # Parse call properties
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

def parse_call_properties(data: bytes) -> Dict[str, Any]:
    properties = {}
    # Binary flag parsing
    if b'\x10\x01' in data:
        properties['direction'] = 'incoming'
    elif b'\x10\x02' in data:
        properties['direction'] = 'outgoing'
    
    # Duration parsing with validation
    duration_match = re.search(rb'duration\x10(\d{1,4})', data)
    if duration_match and validate_duration(int(duration_match.group(1))):
        properties['duration'] = int(duration_match.group(1))
        
    return properties
def export_to_csv(calls: List[Dict], filename: str = 'call_history.csv'):
    """Export call records to CSV file"""
    # Define CSV headers
    headers = [
        'Call ID', 
        'Phone Number', 
        'Name', 
        'Timestamp', 
        'Duration (seconds)', 
        'Call Type',
        'Direction',
        'Junk Confidence',
        'Service'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            # Sort calls by timestamp before writing
            sorted_calls = sorted(calls, key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
            
            for call in sorted_calls:
                writer.writerow({
                    'Call ID': call['id'],
                    'Phone Number': call['number'] if call['number'] else 'Unknown',
                    'Name': call['name'] if call['name'] else '',
                    'Timestamp': call['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if call['timestamp'] else '',
                    'Duration (seconds)': call['duration'] if call['duration'] else '',
                    'Call Type': call['type'] if call['type'] else '',
                    'Direction': call['direction'] if call['direction'] else '',
                    'Junk Confidence': f"{call['junk_confidence']}%" if call['junk_confidence'] is not None else '',
                    'Service': call['service'] if call['service'] else ''
                })
        print(f"\nExported {len(calls)} records to {filename}")
        
    except Exception as e:
        print(f"Error exporting to CSV: {e}")

def main():
    # Open the log file directly
    with open('1F4D44A7-1B7A-4EB8-8B91-48C01F4F4573.log', 'rb') as f:
        raw_data = f.read()

    print("\nAnalyzing Call History Records:")
    metadata = extract_call_metadata(raw_data)
    
    # Print summary statistics
    total_calls = len(metadata['calls'])
    print(f"\nTotal Calls Found: {total_calls}")
    print("\nCall Statistics:")
    for stat, count in metadata['stats'].items():
        print(f"  {stat.title()}: {count}")
    
    # Sort calls by timestamp
    sorted_calls = sorted(metadata['calls'], 
                         key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
    
    # Print earliest and latest timestamps
    if sorted_calls:
        earliest = sorted_calls[0]['timestamp']
        latest = sorted_calls[-1]['timestamp']
        print(f"\nDate Range: {earliest.strftime('%Y-%m-%d %H:%M:%S')} to {latest.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Export to CSV
    export_to_csv(metadata['calls'])
    
    # Print records with pagination
    page_size = 20
    current_page = 1
    total_pages = (total_calls + page_size - 1) // page_size
    
    while True:
        start_idx = (current_page - 1) * page_size
        end_idx = min(start_idx + page_size, total_calls)
        
        print(f"\nShowing records {start_idx + 1}-{end_idx} of {total_calls} (Page {current_page}/{total_pages})")
        print("-" * 80)
        
        for call in sorted_calls[start_idx:end_idx]:
            print(f"\nCall ID: {call['id']}")
            print(f"Number: {call['number']}")
            if call['name']:
                print(f"Name: {call['name']}")
            if call['timestamp']:
                print(f"Time: {call['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            if call['duration']:
                print(f"Duration: {int(call['duration'])} seconds")
            print(f"Type: {call['type']}")
            print(f"Direction: {call['direction']}")
            if call['junk_confidence'] is not None:
                print(f"Junk Confidence: {call['junk_confidence']}%")
            if call['service']:
                print(f"Service: {call['service']}")
        
        print("\nOptions:")
        print("n - Next page")
        print("p - Previous page")
        print("q - Quit")
        print(f"Enter page number (1-{total_pages})")
        
        choice = input("\nEnter choice: ").lower()
        if choice == 'q':
            break
        elif choice == 'n' and current_page < total_pages:
            current_page += 1
        elif choice == 'p' and current_page > 1:
            current_page -= 1
        elif choice.isdigit():
            page = int(choice)
            if 1 <= page <= total_pages:
                current_page = page

if __name__ == '__main__':
    main()
