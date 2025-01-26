import re
import datetime
from typing import Dict, List, Any
import struct
import binascii

def parse_wns_time(data: bytes, start_idx: int) -> datetime.datetime:
    """Parse WNS.time format timestamp from binary data."""
    try:
        # Skip the WNS.time# prefix
        start_idx = start_idx + 9
        
        # Read 8 bytes after the prefix
        timestamp_bytes = data[start_idx:start_idx + 8]
        if len(timestamp_bytes) == 8:
            timestamp = struct.unpack('>d', timestamp_bytes)[0]
            base_date = datetime.datetime(2001, 1, 1)
            return base_date + datetime.timedelta(seconds=timestamp)
    except Exception as e:
        print(f"Error parsing timestamp: {e}")
    return None

def extract_call_records(content: bytes) -> List[Dict[str, Any]]:
    """Extract call records using pattern matching."""
    records = []
    
    # Find all CHTransaction blocks
    transactions = re.finditer(b'CHTransaction.*?(?=CHTransaction|$)', content, re.DOTALL)
    
    for transaction in transactions:
        record = {}
        transaction_data = transaction.group(0)
        
        # Extract phone number (improved pattern)
        phone_match = re.search(rb'\\\\?\+\d{10,}', transaction_data)
        if phone_match:
            record['callerId'] = phone_match.group(0).decode('utf-8').replace('\\', '')
            
        # Extract contact name
        name_match = re.search(rb'_([A-Z\s]+[A-Z])(?=|$)', transaction_data)
        if name_match:
            try:
                name = name_match.group(1).decode('utf-8')
                if len(name) > 3 and not name.startswith('WNS'):  # Filter out non-name matches
                    record['contactName'] = name
            except:
                pass
                
        # Extract UUID
        uuid_match = re.search(rb'\$([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})', transaction_data)
        if uuid_match:
            record['uniqueId'] = uuid_match.group(1).decode('utf-8')
            
        # Extract service name
        if b'com.apple.Telephony' in transaction_data:
            record['serviceType'] = 'com.apple.Telephony'
        elif b'com.apple.FaceTime' in transaction_data:
            record['serviceType'] = 'com.apple.FaceTime'
            
        # Extract call type
        if b'callType' in transaction_data:
            if b'outgoing' in transaction_data.lower():
                record['callType'] = 'outgoing'
            elif b'incoming' in transaction_data.lower():
                record['callType'] = 'incoming'
            elif b'missed' in transaction_data.lower():
                record['callType'] = 'missed'
                
        # Extract timestamp
        time_idx = transaction_data.find(b'WNS.time#')
        if time_idx != -1:
            parsed_time = parse_wns_time(transaction_data, time_idx)
            if parsed_time:
                record['date'] = parsed_time.strftime('%Y-%m-%d %H:%M:%S')
                
        # Extract duration (new pattern)
        duration_match = re.search(rb'duration.*?([0-9]{1,4})', transaction_data)
        if duration_match:
            try:
                duration = int(duration_match.group(1))
                if duration < 10000:  # Filter out unreasonable values
                    record['duration'] = duration
            except:
                pass
                
        # Extract junk confidence (new pattern)
        junk_match = re.search(rb'junkConfidence.*?([0-9]{1,3})', transaction_data)
        if junk_match:
            try:
                confidence = int(junk_match.group(1))
                if confidence <= 100:  # Filter out unreasonable values
                    record['junkConfidence'] = confidence
            except:
                pass
                
        if record:
            records.append(record)
            
    return records

def main():
    log_file = "1F4D44A7-1B7A-4EB8-8B91-48C01F4F4573.log"
    
    try:
        with open(log_file, 'rb') as f:
            content = f.read()
            
        call_records = extract_call_records(content)
        
        print(f"\nFound {len(call_records)} call records")
        for i, record in enumerate(call_records, 1):
            print(f"\nCall Record {i}:")
            for key, value in sorted(record.items()):
                print(f"{key}: {value}")
                
    except Exception as e:
        print(f"Error processing log file: {e}")

if __name__ == "__main__":
    main()
