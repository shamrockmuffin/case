import biplist
import io
import re
import struct
import uuid
from datetime import datetime, timedelta
import logging
import binascii
import json
import os
import sqlite3
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_wns_time(wns_time_bytes):
    """Parses WNS.time from bytes to a datetime object."""
    seconds_since_reference = struct.unpack('>d', wns_time_bytes)[0]
    reference_date = datetime(2001, 1, 1)
    return reference_date + timedelta(seconds=seconds_since_reference)

def decode_call_record(hex_data):
    """Decodes a single call record from hex data."""
    try:
        # Remove any non-hex characters and convert to bytes.
        hex_data = re.sub(r'[^0-9a-fA-F]', '', hex_data)
        binary_data = bytes.fromhex(hex_data)
    
        # Use biplist to decode the binary plist data
        plist = biplist.read(io.BytesIO(binary_data))
        
        # Check if the decoded plist is a dictionary
        if not isinstance(plist, dict):
            logging.warning("Decoded plist is not a dictionary.")
            return None

        # Extract the relevant data from the plist
        # If 'root' is not in the plist, then it's not a valid call record.
        if 'root' not in plist:
            logging.warning("Decoded plist does not contain 'root' key.")
            return None

        # Check if root is of type dict
        if not isinstance(plist['root'], dict):
          logging.warning("Root is not a dictionary.")
          return None

        call_record = plist['root']
        
        # Initialize a dictionary to hold the decoded data
        decoded_record = {}

        # Iterate through all the keys and values, looking for the known keys to extract the data
        for key, value in call_record.items():
             if key == 'unreadCount':
                  decoded_record['unreadCount'] = value
             elif key == 'handleType':
                  decoded_record['handleType'] = value
             elif key == 'callStatus':
                  decoded_record['callStatus'] = value
             elif key == 'isoCountryCode':
                  decoded_record['isoCountryCode'] = value
             elif key == 'serviceRadar':
                  decoded_record['serviceRadar'] = value
             elif key == 'duration':
                 decoded_record['duration'] = value
             elif key == 'uniqueId':
                 decoded_record['uniqueId'] = value
             elif key == 'callerIdAvailability':
                 decoded_record['callerIdAvailability'] = value
             elif key == 'bytesOfDataUsed':
                 decoded_record['bytesOfDataUsed'] = value
             elif key == 'callCategory':
                 decoded_record['callCategory'] = value
             elif key == 'verificationStatus':
                 decoded_record['verificationStatus'] = value
             elif key == 'devicePhoneId':
                 decoded_record['devicePhoneId'] = value
             elif key == 'localParticipantUUID':
                 if isinstance(value, bytes):
                     decoded_record['localParticipantUUID'] = str(uuid.UUID(bytes=value))
                 else:
                     decoded_record['localParticipantUUID'] = value
             elif key == 'mobileCountryCode':
                decoded_record['mobileCountryCode'] = value
             elif key == 'remoteParticipantHandles':
                  decoded_record['remoteParticipantHandles'] = value
             elif key == 'imageURL':
                  decoded_record['imageURL'] = value
             elif key == 'name':
                  decoded_record['name'] = value
             elif key == 'date':
                 #If the date is stored as bytes convert it to datetime
                 if isinstance(value, bytes):
                   decoded_record['date'] = parse_wns_time(value)
                 else:
                   decoded_record['date'] = value
             elif key == 'hasMessage':
                  decoded_record['hasMessage'] = value
             elif key == 'conversationIDX':
                  decoded_record['conversationIDX'] = value
             elif key == 'callerId':
                  decoded_record['callerId'] = value
             elif key == 'callType':
                  decoded_record['callType'] = value
             elif key == 'participantGroupUUID':
                 if isinstance(value, bytes):
                     decoded_record['participantGroupUUID'] = str(uuid.UUID(bytes=value))
                 else:
                     decoded_record['participantGroupUUID'] = value
             elif key == 'read':
                  decoded_record['read'] = value
             elif key == 'junkConfidence':
                decoded_record['junkConfidence'] = value
             elif key == 'callerIdLocation':
                 decoded_record['callerIdLocation'] = value
             elif key == 'timeToEstablish':
                 decoded_record['timeToEstablish'] = value
             elif key == 'disconnectedCause':
                  decoded_record['disconnectedCause'] = value
             elif key == 'junkIdentificationCategory':
                  decoded_record['junkIdentificationCategory'] = value
             elif key == 'mobileNetworkCode':
                 decoded_record['mobileNetworkCode'] = value
             elif key == 'outgoingLocalParticipantUUID':
                 if isinstance(value, bytes):
                     decoded_record['outgoingLocalParticipantUUID'] = str(uuid.UUID(bytes=value))
                 else:
                     decoded_record['outgoingLocalParticipantUUID'] = value
             elif key == 'mediaType':
                 decoded_record['mediaType'] = value
             #Add other fields if needed

        return decoded_record
    except biplist.InvalidPlistException as e:
        logging.error(f"Invalid bplist format: {e}")
        return None
    except struct.error as e:
        logging.error(f"Struct error: {e}")
        return None
    except Exception as e:
        logging.error(f"Error decoding record: {e}")
        return None

def find_bplist_chunks(data):
    """Find chunks of data that look like binary plists."""
    chunks = []
    offset = 0
    while True:
        # Look for bplist00 marker
        idx = data.find(b'bplist00', offset)
        if idx == -1:
            break
            
        # Try to find the end of this chunk by looking for the next bplist00 marker
        next_idx = data.find(b'bplist00', idx + 8)
        if next_idx == -1:
            # If no next marker, take all remaining data
            chunk = data[idx:]
        else:
            chunk = data[idx:next_idx]
            
        chunks.append(chunk)
        offset = idx + 8
        
        if next_idx == -1:
            break
            
    return chunks

def inspect_table_schema(cursor, table_name):
    """Get the schema for a specific table."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        return [col[1] for col in columns]  # Column names are in index 1
    except sqlite3.OperationalError as e:
        logging.error(f"Error getting schema for {table_name}: {e}")
        return []

def try_sqlite_read(filepath):
    """Attempt to read file as SQLite database and extract call history records."""
    try:
        conn = sqlite3.connect(filepath)
        cursor = conn.cursor()
        
        # Try to get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        records = []
        if tables:
            logging.info(f"Found tables in {filepath}: {tables}")
            
            # First inspect the ZCALLRECORD table schema
            call_table = 'ZCALLRECORD'
            columns = inspect_table_schema(cursor, call_table)
            logging.info(f"Columns in {call_table}: {columns}")
            
            # Build query with all relevant fields
            query = """
                SELECT 
                    ZADDRESS as number,
                    ZDATE as timestamp,
                    ZDURATION as duration,
                    ZORIGINATED as is_outgoing,
                    ZANSWERED as is_answered,
                    ZCALLTYPE as call_type,
                    ZNAME as contact_name,
                    ZLOCATION as location,
                    ZSERVICE_PROVIDER as service_provider,
                    ZISO_COUNTRY_CODE as country_code,
                    ZJUNKCONFIDENCE as spam_confidence,
                    ZDISCONNECTED_CAUSE as disconnect_reason,
                    ZUNIQUE_ID as call_id
                FROM ZCALLRECORD 
                ORDER BY ZDATE DESC
            """
            
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
                column_names = [description[0] for description in cursor.description]
                
                for row in rows:
                    record = dict(zip(column_names, row))
                    
                    # Convert timestamp
                    if 'timestamp' in record and record['timestamp']:
                        try:
                            timestamp = float(record['timestamp'])
                            record['timestamp'] = datetime(2001, 1, 1) + timedelta(seconds=timestamp)
                        except:
                            pass
                            
                    # Convert duration to readable format
                    if 'duration' in record and record['duration']:
                        try:
                            duration_secs = int(float(record['duration']))
                            hours = duration_secs // 3600
                            minutes = (duration_secs % 3600) // 60
                            seconds = duration_secs % 60
                            record['duration_formatted'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        except:
                            pass
                            
                    # Convert boolean fields
                    if 'is_outgoing' in record:
                        record['call_direction'] = 'Outgoing' if record['is_outgoing'] else 'Incoming'
                    if 'is_answered' in record:
                        record['status'] = 'Answered' if record['is_answered'] else 'Missed/Rejected'
                            
                    records.append(record)
                
                logging.info(f"Successfully extracted {len(rows)} records from {call_table}")
                
                # Print summary of first few records
                if records:
                    logging.info("\nSample of extracted records:")
                    for i, record in enumerate(records[:5]):
                        logging.info(f"\nRecord {i+1}:")
                        for key, value in record.items():
                            if value is not None and value != '':
                                logging.info(f"  {key}: {value}")
                    
                    # Print date range
                    timestamps = [r['timestamp'] for r in records if 'timestamp' in r and r['timestamp']]
                    if timestamps:
                        min_date = min(timestamps)
                        max_date = max(timestamps)
                        logging.info(f"\nDate range: {min_date} to {max_date}")
                        
                    # Print call statistics
                    total_calls = len(records)
                    outgoing_calls = sum(1 for r in records if r.get('is_outgoing'))
                    incoming_calls = total_calls - outgoing_calls
                    answered_calls = sum(1 for r in records if r.get('is_answered'))
                    missed_calls = total_calls - answered_calls
                    
                    logging.info("\nCall Statistics:")
                    logging.info(f"  Total Calls: {total_calls}")
                    logging.info(f"  Outgoing Calls: {outgoing_calls}")
                    logging.info(f"  Incoming Calls: {incoming_calls}")
                    logging.info(f"  Answered Calls: {answered_calls}")
                    logging.info(f"  Missed/Rejected Calls: {missed_calls}")
                    
                    # Get unique numbers and their call counts
                    number_stats = {}
                    for record in records:
                        number = record.get('number')
                        if number:
                            if number not in number_stats:
                                number_stats[number] = {
                                    'count': 0,
                                    'name': record.get('contact_name'),
                                    'last_call': record.get('timestamp')
                                }
                            number_stats[number]['count'] += 1
                    
                    # Print top 10 most frequent numbers
                    logging.info("\nTop 10 Most Frequent Numbers:")
                    sorted_numbers = sorted(number_stats.items(), key=lambda x: x[1]['count'], reverse=True)
                    for number, stats in sorted_numbers[:10]:
                        name = f" ({stats['name']})" if stats['name'] else ""
                        logging.info(f"  {number}{name}: {stats['count']} calls")
                        
            except sqlite3.OperationalError as e:
                logging.error(f"Error querying {call_table}: {e}")
        
        if records:
            # Save the extracted records
            with open("decoded_calls.json", "w") as f:
                json.dump(records, f, indent=2, default=str)
            logging.info(f"\nSaved {len(records)} records to decoded_calls.json")
            return True
            
        return False
    except sqlite3.DatabaseError as e:
        logging.error(f"SQLite error: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass

def clean_bplist_chunk(chunk):
    """Clean a binary plist chunk by removing UTF-8 BOM and other encoding artifacts."""
    # Remove UTF-8 BOM if present
    if chunk.startswith(b'\xef\xbb\xbf'):
        chunk = chunk[3:]
    
    # Remove any other non-binary plist data before the header
    bplist_start = chunk.find(b'bplist00')
    if bplist_start >= 0:
        chunk = chunk[bplist_start:]
        
    return chunk

def main():
    """
    Main function to read call history data from various sources.
    """
    try:
        # First try reading as SQLite database
        if try_sqlite_read("CallHistory.storedata"):
            logging.info("Successfully processed SQLite database")
            return
            
        # If SQLite fails, try reading as binary file
        with open("CallHistory.storedata", "rb") as f:
            data = f.read()
            
        # Find all binary plist chunks
        chunks = []
        offset = 0
        while True:
            idx = data.find(b'bplist00', offset)
            if idx == -1:
                break
                
            # Look for the next marker or end of file
            next_idx = data.find(b'bplist00', idx + 8)
            if next_idx == -1:
                chunk = data[idx:]
            else:
                chunk = data[idx:next_idx]
                
            # Clean the chunk
            chunk = clean_bplist_chunk(chunk)
            
            if len(chunk) > 8:  # Must be longer than 'bplist00'
                chunks.append(chunk)
                
            if next_idx == -1:
                break
            offset = idx + 8
            
        logging.info(f"Found {len(chunks)} potential plist chunks")
        
        decoded_records = []
        for i, chunk in enumerate(chunks):
            try:
                plist = biplist.readPlistFromString(chunk)
                if isinstance(plist, dict):
                    decoded = decode_call_record({'root': plist})
                    if decoded:
                        decoded_records.append(decoded)
                        logging.info(f"Successfully decoded chunk {i}")
            except Exception as e:
                logging.debug(f"Failed to decode chunk {i}: {e}")
                
        if decoded_records:
            logging.info(f"Successfully decoded {len(decoded_records)} records")
            with open("decoded_calls.json", "w") as f:
                json.dump(decoded_records, f, indent=2, default=str)
            logging.info("Saved decoded records to decoded_calls.json")
            
            if len(decoded_records) > 0:
                logging.info("Example of first decoded record:")
                print(json.dumps(decoded_records[0], indent=2, default=str))
        else:
            logging.warning("No valid records found")
            
    except FileNotFoundError:
        logging.error("CallHistory.storedata file not found")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()