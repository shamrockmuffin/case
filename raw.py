import biplist
import io
import re
import struct
from datetime import datetime, timedelta

def parse_wns_time(wns_time_bytes):
    """Parses WNS.time from bytes to a datetime object.
    
       Note: The reference date for WNS.time format (number of seconds since a specific reference date) is not
             provided in the sources. The value used below (2001/01/01) is the Mac/Cocoa reference date and
             the correct one for this format. It is not found in the sources and may need independent verification.
    """
    seconds_since_reference = struct.unpack('>d', wns_time_bytes)
    reference_date = datetime(2001, 1, 1)
    return reference_date + timedelta(seconds=seconds_since_reference)


def decode_call_record(hex_data):
    """
    Decodes a single call record from hex data.
    
    Args:
        hex_data: A string containing the hex representation of a single call record.

    Returns:
        A dictionary containing the decoded data or None if the record can't be decoded.
    """
    try:
        # Remove any non-hex characters and convert to bytes.
        hex_data = re.sub(r'[^0-9a-fA-F]', '', hex_data)
        binary_data = bytes.fromhex(hex_data)
    
        # Use biplist to decode the binary plist data
        plist = biplist.read(io.BytesIO(binary_data))
        
        # Check if the decoded plist is a dictionary
        if not isinstance(plist, dict):
           return None

        # Extract the relevant data from the plist
        # If 'root' is not in the plist, then it's not a valid call record.
        if 'root' not in plist:
            return None

        # Check if root is of type dict
        if not isinstance(plist['root'], dict):
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
                 decoded_record['outgoingLocalParticipantUUID'] = value
             elif key == 'mediaType':
                 decoded_record['mediaType'] = value
             #Add other fields if needed


        return decoded_record
    except Exception as e:
        print(f"Error decoding record: {e}")
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

    for record in records:
        decoded_record = decode_call_record(record)
        if decoded_record:
          decoded_records.append(decoded_record)
    
    # Print the decoded records
    for record in decoded_records:
      print(record)

if __name__ == "__main__":
    main()