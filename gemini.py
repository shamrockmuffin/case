import struct
import csv
from datetime import datetime, timedelta
import logging
import re
import uuid
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def find_next_record(data: bytes, start: int) -> tuple[int, int]:
    """Find the next record boundaries."""
    try:
        # Find start of record
        pos = data.find(b'CHTransaction', start)
        if pos == -1:
            return -1, -1
            
        # Find end of record (next CHTransaction or end of file)
        next_pos = data.find(b'CHTransaction', pos + 12)
        if next_pos == -1:
            next_pos = len(data)
            
        return pos, next_pos
    except Exception as e:
        logger.error(f"Error finding record boundaries: {e}")
        return -1, -1

def extract_uuid(data: bytes) -> str:
    """Extract UUID from data."""
    try:
        pattern = rb'([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})'
        match = re.search(pattern, data, re.IGNORECASE)
        if match:
            uuid_str = match.group(1).decode('utf-8')
            try:
                uuid.UUID(uuid_str)
                return uuid_str
            except:
                pass
        return None
    except Exception as e:
        logger.error(f"Error extracting UUID: {e}")
        return None

def extract_phone_number(data, pos):
    """Extract phone number from data."""
    try:
        # Look for phone number pattern
        phone_pattern = rb'\+\d{10,}'
        for i in range(pos, min(pos + 200, len(data))):
            match = re.search(phone_pattern, data[i:i+20])
            if match:
                return match.group(0).decode('utf-8')
        return None
    except Exception as e:
        logger.error(f"Error extracting phone number: {e}")
        return None

def extract_timestamp(data: bytes) -> datetime:
    """Extract timestamp from data."""
    try:
        # Look for WNS.time# marker
        pos = data.find(b'WNS.time#')
        if pos != -1:
            # Skip the WNS.time# prefix and read 8 bytes
            timestamp_bytes = data[pos+9:pos+17]
            if len(timestamp_bytes) == 8:
                timestamp = struct.unpack('>d', timestamp_bytes)[0]
                return datetime(2001, 1, 1) + timedelta(seconds=timestamp)
        return None
    except Exception as e:
        logger.error(f"Error extracting timestamp: {e}")
        return None

def extract_duration(data, pos):
    """Extract call duration in seconds from data."""
    try:
        # Look for duration value in NSKeyedArchiver plist
        # Duration is often stored as a number after 'duration' key
        for i in range(pos, min(pos + 500, len(data))):
            # Look for duration value in binary format
            # Try little-endian 32-bit integer
            try:
                val = struct.unpack('<I', data[i:i+4])[0]
                if 1 <= val <= 7200:  # Between 1 second and 2 hours
                    return float(val)
            except:
                pass
                
            # Try little-endian 32-bit float
            try:
                val = struct.unpack('<f', data[i:i+4])[0]
                if 1.0 <= val <= 7200.0:  # Between 1 second and 2 hours
                    return float(val)
            except:
                pass
                
            # Try big-endian 32-bit integer
            try:
                val = struct.unpack('>I', data[i:i+4])[0]
                if 1 <= val <= 7200:  # Between 1 second and 2 hours
                    return float(val)
            except:
                pass
                
            # Try big-endian 32-bit float
            try:
                val = struct.unpack('>f', data[i:i+4])[0]
                if 1.0 <= val <= 7200.0:  # Between 1 second and 2 hours
                    return float(val)
            except:
                pass
                
        return 0  # Default if no valid duration found
    except Exception as e:
        logger.error(f"Error extracting duration: {e}")
        return 0

def process_file(filename):
    try:
        # Read the file
        logger.info(f"Reading file: {filename}")
        with open(filename, 'rb') as f:
            data = f.read()
            
        records = []
        pos = 0
        seen_uuids = set()  # Track unique UUIDs
        
        # Process each record
        while True:
            # Find next record
            start, end = find_next_record(data, pos)
            if start == -1:
                break
                
            # Extract record data
            record_data = data[start:end]
            
            # Parse record fields
            record = {
                'uuid': extract_uuid(record_data),
                'caller_id': extract_phone_number(record_data, start),
                'timestamp': extract_timestamp(record_data),
                'duration': extract_duration(record_data, start)
            }
            
            # Determine call type
            if b'com.apple.Telephony' in record_data:
                record['call_type'] = 'cellular'
            elif b'com.apple.FaceTime' in record_data:
                record['call_type'] = 'facetime'
            else:
                record['call_type'] = 'unknown'
                
            # Validate record and check for duplicate UUIDs
            if record['uuid'] and record['timestamp']:
                if record['uuid'] not in seen_uuids:
                    seen_uuids.add(record['uuid'])
                    records.append(record)
                else:
                    logger.warning(f"Duplicate UUID found: {record['uuid']}")
                
            pos = end
            
        logger.info(f"Found {len(records)} records with unique UUIDs")
        return records
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return []

def export_to_csv(records, output_file='call_history.csv'):
    if not records:
        logger.warning("No records to export")
        return
        
    try:
        fieldnames = ['uuid', 'timestamp', 'caller_id', 'call_type', 'duration']
                     
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Sort records by timestamp
            sorted_records = sorted(records, 
                                 key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
            
            for record in sorted_records:
                # Convert timestamp to string
                if isinstance(record['timestamp'], datetime):
                    record['timestamp'] = record['timestamp'].isoformat()
                writer.writerow(record)
            
        logger.info(f"Exported {len(records)} records to {output_file}")
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")

def format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS.mmm format."""
    if seconds == 0:
        return "00:00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    elif minutes > 0:
        return f"{minutes:02d}:{seconds:06.3f}"
    else:
        return f"00:{seconds:06.3f}"

def export_to_json(records, output_file='decoded_calls.json'):
    if not records:
        logger.warning("No records to export to JSON")
        return
        
    try:
        json_records = []
        for record in records:
            # Handle timestamp
            if isinstance(record['timestamp'], datetime):
                timestamp_str = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')
            else:
                timestamp_str = record['timestamp']  # Already a string
            
            # Format duration
            duration = record.get('duration', 0.0)
            
            # Create JSON record with matching format
            json_record = {
                "number": record['caller_id'].replace('+1', '') if record['caller_id'] else None,
                "timestamp": timestamp_str,
                "duration": duration,
                "duration_formatted": format_duration(duration),
                "is_outgoing": 0,  # Default since we don't have direction info
                "is_answered": 1,  # Default since we don't have status info
                "call_type": 8 if record['call_type'] == 'facetime' else 1,
                "contact_name": None,
                "location": None,
                "service_provider": "com.apple.FaceTime" if record['call_type'] == 'facetime' else "com.apple.Telephony",
                "country_code": "us" if record['call_type'] == 'cellular' else None,
                "spam_confidence": 0,
                "disconnect_reason": 0,
                "call_id": record['uuid'],
                "call_direction": "Unknown",
                "status": "Unknown"
            }
            json_records.append(json_record)
            
        # Sort records by timestamp
        json_records.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_records, f, indent=2)
            
        logger.info(f"Exported {len(json_records)} records to {output_file}")
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")

def main():
    input_file = '1F4D44A7-1B7A-4EB8-8B91-48C01F4F4573.log'
    records = process_file(input_file)
    export_to_csv(records)
    export_to_json(records)

if __name__ == '__main__':
    main()