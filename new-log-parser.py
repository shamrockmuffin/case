import re
import struct
import datetime
import tkinter as tk
from tkinter import ttk, filedialog
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import pandas as pd
from pathlib import Path

@dataclass
class CallRecord:
    """Structured call record data."""
    uuid: Optional[str] = None
    phone_number: Optional[str] = None
    contact_name: Optional[str] = None
    timestamp: Optional[datetime.datetime] = None
    duration: Optional[int] = None
    call_type: Optional[str] = None
    direction: Optional[str] = None
    junk_confidence: Optional[int] = None
    service: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'Call ID': self.uuid,
            'Phone Number': self.phone_number,
            'Name': self.contact_name,
            'Timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None,
            'Duration (seconds)': self.duration,
            'Call Type': self.call_type,
            'Direction': self.direction,
            'Junk Confidence': f"{self.junk_confidence}%" if self.junk_confidence is not None else None,
            'Service': self.service
        }

def parse_wns_time(data: bytes, start_idx: int) -> Optional[datetime.datetime]:
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

def standardize_phone_number(phone: str) -> Optional[str]:
    """Standardize phone number to format: +1XXXXXXXXXX"""
    if not phone:
        return None
        
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Handle different formats
    if len(digits) == 10:  # Standard US number without country code
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):  # US number with country code
        return f"+{digits}"
    elif len(digits) == 11:  # Other format with 11 digits
        return f"+1{digits[-10:]}"  # Take last 10 digits
    elif len(digits) > 11:  # Longer number
        if digits.startswith('1'):
            return f"+{digits[:11]}"  # Take first 11 digits if starts with 1
        else:
            return f"+1{digits[:10]}"  # Take first 10 digits and add +1
    
    return None  # Return None for invalid numbers

def parse_call_logs(log_content: bytes) -> List[Dict[str, Any]]:
    """Parse call logs from binary content."""
    records = []
    
    # Find all CHTransaction blocks
    transactions = re.finditer(b'CHTransaction.*?(?=CHTransaction|$)', log_content, re.DOTALL)
    
    for transaction in transactions:
        record = {
            'UUID': None,
            'Secondary_UUID': None,
            'NS_UUID': None,
            'Phone Number': None,
            'Timestamp': None,
            'Total Calls': None,
            'Call Type': None,
            'Service': None,
            'Caller Name': None,
            'App ID': None,
            'Class Name': None,
            'Display ID': None
        }
        data = transaction.group(0)
        
        # Extract both upper and lower case UUIDs
        uuid_patterns = [
            # Upper case UUID pattern (primary)
            rb'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})',
            # Lower case UUID pattern (secondary)
            rb'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
        ]
        
        # Find all UUIDs in the data
        found_uuids = {'upper': [], 'lower': []}
        for pattern, case in [(uuid_patterns[0], 'upper'), (uuid_patterns[1], 'lower')]:
            matches = re.finditer(pattern, data)
            for match in matches:
                uuid = match.group(1).decode('utf-8').strip()
                if uuid and uuid not in found_uuids[case]:
                    found_uuids[case].append(uuid)
        
        # Assign UUIDs to appropriate fields
        if found_uuids['upper']:
            record['UUID'] = found_uuids['upper'][0]
        if found_uuids['lower']:
            record['Secondary_UUID'] = found_uuids['lower'][0]
        
        # Accept record if either UUID is present
        if record['UUID'] or record['Secondary_UUID']:
            # Extract NS.uuidbytes and display ID using a more robust pattern
            ns_uuid_match = re.search(rb'NS\.uuidbytesO(.*?)(?:\\|$)', data)
            if ns_uuid_match:
                record['NS_UUID'] = ns_uuid_match.group(0).decode('utf-8', errors='ignore').strip()
                
                # Look for text after NS.uuidbytes that might be a display ID
                display_pattern = rb'NS\.uuidbytesO.*?\\([A-Za-z0-9\s\+\.]+?)(?:\\|$)'
                display_match = re.search(display_pattern, data)
                if display_match and len(display_match.groups()) > 0:
                    display_id = display_match.group(1).decode('utf-8', errors='ignore').strip()
                    if display_id and not any(x in display_id for x in ('NS.', 'RS', 'PQ')):
                        record['Display ID'] = display_id or None  # Convert empty string to None
            
            # Extract phone number with stricter validation
            phone_match = re.search(rb'\+?1?([0-9]{10,})', data)
            if phone_match:
                raw_number = phone_match.group(0).decode('utf-8').strip()
                standardized = standardize_phone_number(raw_number)
                record['Phone Number'] = standardized if standardized else None
            
            # Extract caller name with improved validation
            name_matches = re.finditer(rb'(?:WIRELESS CALLER|CLAIM ASSIST SO|Spam Risk|[A-Z][A-Za-z\s\+\.]+(?:\s[A-Z][A-Za-z\s\+\.]+)?)', data)
            for match in name_matches:
                potential_name = match.group(0).decode('utf-8').strip()
                if potential_name and not any(x in potential_name for x in ('NS.', 'RS', 'PQ', 'None')):
                    record['Caller Name'] = potential_name
                    break
            
            # Extract service type - strict matching only
            if b'com.apple.Telephony' in data:
                record['Service'] = 'Phone'
                record['App ID'] = 'com.apple.Telephony'
            elif b'com.apple.FaceTime' in data:
                record['Service'] = 'FaceTime Video'
                record['App ID'] = 'com.apple.FaceTime'
            # No default/fallback case - if we don't explicitly recognize the service, leave it as None
            
            # Extract timestamp
            time_idx = data.find(b'WNS.time#')
            if time_idx != -1:
                timestamp = parse_wns_time(data, time_idx)
                if timestamp:
                    record['Timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            # Determine call type
            if b'outgoing' in data.lower():
                record['Call Type'] = 'Outgoing'
            elif b'incoming' in data.lower():
                record['Call Type'] = 'Incoming'
            elif b'missed' in data.lower():
                record['Call Type'] = 'Missed'
            
            # Final validation
            if record['UUID'] or record['Secondary_UUID']:  # Only add records with a valid UUID
                records.append(record)
    
    return records

def process_log_file(file_path: str) -> List[Dict[str, Any]]:
    """Process a single log file and return parsed records."""
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        records = parse_call_logs(content)
        
        # Enhanced deduplication using multiple identifiers
        unique_records = []
        seen_combinations = set()
        
        for record in records:
            # Create a comprehensive deduplication key tuple
            dedup_key = (
                record.get('UUID', ''),
                record.get('Secondary_UUID', ''),
                record.get('Phone Number', ''),
                record.get('Timestamp', ''),
                record.get('Call Type', ''),
                record.get('Service', '')
            )
            
            # Skip if we've seen this exact combination before
            if dedup_key in seen_combinations:
                continue
                
            # Only add records with valid UUID
            if record.get('UUID') or record.get('Secondary_UUID'):
                seen_combinations.add(dedup_key)
                unique_records.append(record)
        
        # Sort records by timestamp (newest first) if available
        unique_records.sort(
            key=lambda x: x.get('Timestamp', ''),
            reverse=True
        )
        
        # Add deduplication statistics to the first record if records exist
        if unique_records:
            duplicates_removed = len(records) - len(unique_records)
            unique_records[0]['Duplicates Removed'] = duplicates_removed
        
        return unique_records
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return []

def create_forensic_viewer(records: List[Dict[str, Any]]):
    """Create a forensic viewer window for call records."""
    root = ttk.Window(
        title="Call Log Forensic Viewer",
        themename="darkly",
        size=(1600, 900)
    )
    
    # Create main container with padding
    container = ttk.Frame(root)
    container.pack(fill=BOTH, expand=YES, padx=10, pady=5)
    
    # Top frame for search and export
    top_frame = ttk.Frame(container)
    top_frame.pack(fill=X, pady=(0, 5))
    
    # Search frame with label
    search_frame = ttk.LabelFrame(top_frame, text="Search", padding=5)
    search_frame.pack(side=LEFT, fill=X, expand=YES)
    
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(fill=X, expand=YES, padx=5)
    
    # Export button
    export_btn = ttk.Button(
        top_frame,
        text="Export to CSV",
        command=lambda: export_to_csv(records),
        style="info.TButton",
        width=15
    )
    export_btn.pack(side=RIGHT, padx=(10, 0))
    
    # Statistics frame
    stats_frame = ttk.LabelFrame(container, text="Call Statistics", padding=5)
    stats_frame.pack(fill=X, pady=(0, 5))
    
    # Calculate statistics
    stats = {
        'Total Calls': len(records),
        'Unique Numbers': len(set(r['Phone Number'] for r in records if r['Phone Number'])),
        'Total Primary UUIDs': len(set(r['UUID'] for r in records if r['UUID'])),
        'Total Secondary UUIDs': len(set(r['Secondary_UUID'] for r in records if r['Secondary_UUID'])),
        'Incoming': sum(1 for r in records if r.get('Call Type') == 'Incoming'),
        'Outgoing': sum(1 for r in records if r.get('Call Type') == 'Outgoing'),
        'Missed': sum(1 for r in records if r.get('Call Type') == 'Missed'),
        'Phone': sum(1 for r in records if r.get('Service') == 'Phone'),
        'FaceTime': sum(1 for r in records if r.get('Service') == 'FaceTime Video')
    }
    
    # Create grid of statistics
    stat_grid = ttk.Frame(stats_frame)
    stat_grid.pack(fill=X, expand=YES)
    
    for i, (label, value) in enumerate(stats.items()):
        col = i % 4
        row = i // 4
        ttk.Label(
            stat_grid,
            text=f"{label}: {value}",
            style="info.TLabel"
        ).grid(row=row, column=col, padx=20, pady=2, sticky='w')
    
    # Create frame for treeview and scrollbar
    tree_frame = ttk.Frame(container)
    tree_frame.pack(fill=BOTH, expand=YES)
    
    # Columns configuration
    columns = (
        "UUID", "Secondary_UUID", "Phone Number", "Caller Name", "Display ID",
        "Timestamp", "Call Type", "Service"
    )
    
    # Create treeview with scrollbars
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=25)
    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    
    # Grid layout for treeview and scrollbars
    tree.grid(column=0, row=0, sticky='nsew')
    vsb.grid(column=1, row=0, sticky='ns')
    hsb.grid(column=0, row=1, sticky='ew')
    
    # Configure grid weights
    tree_frame.grid_columnconfigure(0, weight=1)
    tree_frame.grid_rowconfigure(0, weight=1)
    
    # Configure column widths and headings
    column_widths = {
        "UUID": 250,
        "Secondary_UUID": 250,  # Added width for secondary UUID
        "Phone Number": 120,
        "Caller Name": 150,
        "Display ID": 150,
        "Timestamp": 150,
        "Call Type": 80,
        "Service": 100
    }
    
    for col in columns:
        tree.heading(col, text=col, command=lambda c=col: sort_treeview(tree, c, False))
        tree.column(col, width=column_widths[col], minwidth=50)
    
    # Insert records
    for record in records:
        values = [record.get(col, "") for col in columns]
        tree.insert("", END, values=values)
    
    def search_records(*args):
        query = search_var.get().lower()
        tree.delete(*tree.get_children())
        for record in records:
            if any(str(value).lower().find(query) >= 0 for value in record.values()):
                values = [record.get(col, "") for col in columns]
                tree.insert("", END, values=values)
    
    search_var.trace('w', search_records)
    
    def sort_treeview(tree, col, reverse):
        l = [(tree.set(k, col), k) for k in tree.get_children("")]
        try:
            l.sort(key=lambda x: float(x[0]) if x[0].replace('.','').isdigit() else x[0].lower(), 
                  reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)
        for index, (_, k) in enumerate(l):
            tree.move(k, "", index)
        tree.heading(col, command=lambda: sort_treeview(tree, col, not reverse))
    
    def export_to_csv(records):
        file_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            # Create DataFrame with only visible columns
            visible_records = [{col: record.get(col, "") for col in columns} 
                             for record in records]
            df = pd.DataFrame(visible_records)
            df.to_csv(file_path, index=False)
            
            # Show success message
            ttk.dialogs.Messagebox.show_info(
                message=f"Data exported successfully to {file_path}",
                title="Export Complete"
            )
    
    # Set focus to search entry
    search_entry.focus_set()
    
    return root

def main():
    """Main entry point for processing log files."""
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python new-log-parser.py <log_file_path>")
        sys.exit(1)
        
    log_file = sys.argv[1]
    records = process_log_file(log_file)
    
    # Launch the forensic viewer and start mainloop
    root = create_forensic_viewer(records)
    root.mainloop()

if __name__ == "__main__":
    main()