
import biplist
import io
import re
import struct
import uuid
from datetime import datetime, timedelta
import logging
import csv
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_wns_time(wns_time_bytes):
    """Parses WNS.time from bytes to a datetime object."""
    seconds_since_reference = struct.unpack('>d', wns_time_bytes)[0]
    reference_date = datetime(2001, 1, 1)
    return reference_date + timedelta(seconds=seconds_since_reference)

def parse_field_length(data: bytes, start_idx: int) -> tuple[int, int]:
    """Parse field length marker and return tuple of (length, bytes_consumed)."""
    if data[start_idx] == 0x10:  # Single byte length marker
        return data[start_idx + 1], 2
    elif data[start_idx] == 0x11:  # Two byte length marker
        length = (data[start_idx + 1] << 8) | data[start_idx + 2]
        return length, 3
    return 0, 0

def decode_call_record(hex_data):
    """Decodes a single call record from hex data."""
    try:
        # Remove any non-hex characters and convert to bytes.
        hex_data = re.sub(r'[^0-9a-fA-F]', '', hex_data)
        binary_data = bytes.fromhex(hex_data)
    
        # Use biplist to decode the binary plist data
        plist = biplist.read(io.BytesIO(binary_data))
        return plist
    except biplist.InvalidPlistException as e:
        logging.error(f"Invalid bplist format: {e}")
        return None
    except struct.error as e:
        logging.error(f"Struct error: {e}")
        return None
    except Exception as e:
        logging.error(f"Error decoding record: {e}")
        return None


def main():
    """
    Main function to read the raw.txt data, split into records, and decode each record.
    """
    
    with open("raw.txt", "r", encoding="utf-8") as f:
      hex_data = f.read()
    
    # Split the hex data by the bplist00 marker, remove any empty strings
    records = re.split(r'(?<=62706C6973743030)', hex_data)
    records = [record for record in records if record]
    
    decoded_records = []
    
    for i, record in enumerate(records):
        # Remove any non-hex characters and convert to bytes.
        record = re.sub(r'[^0-9a-fA-F]', '', record)
        decoded_record = decode_call_record(record)
        if decoded_record:
            decoded_records.append(decoded_record)
        else:
            logging.warning(f"Failed to decode record at index: {i}")

    # Print the decoded records
    for i, record in enumerate(decoded_records):
        print(f"Record {i+1}:")
        print(record)
        print("-" * 40)

if __name__ == "__main__":
    main()