import pandas as pd
import sqlite3
from datetime import datetime

def standardize_phone_number(phone):
    """Standardize phone number format to include '+1' prefix if missing"""
    try:
        phone = str(phone).strip()
        if not phone.startswith('+1'):
            if phone.startswith('1'):
                return '+' + phone
            return '+1' + phone
        return phone
    except Exception as e:
        print(f"Error standardizing phone number: {e}")
        return phone

def create_database():
    # Create/connect to SQLite database
    conn = sqlite3.connect('call_history.db')
    cursor = conn.cursor()
    
    # Drop existing views and tables
    cursor.execute('DROP VIEW IF EXISTS call_summary')
    cursor.execute('DROP TABLE IF EXISTS call_history')
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS call_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        call_type TEXT,
        service TEXT,
        source TEXT NOT NULL,
        contact_name TEXT
    )
    ''')
    
    # Create indices for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_phone_number ON call_history(phone_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON call_history(timestamp)')
    
    try:
        # Read JPREGCALL CSV for contact names
        jpreg_df = pd.read_csv('JPREGCALL.csv')
        jpreg_df['Number'] = jpreg_df['Number'].apply(standardize_phone_number)
        # Create a dictionary of phone numbers to contact names, keeping only the most recent contact name for each number
        contact_dict = {}
        for _, row in jpreg_df.iterrows():
            phone = row['Number']
            contact = row['Contact']
            if contact and not contact.startswith('+') and not contact.isdigit():
                contact_dict[phone] = contact
        
        # Read Call History CSV
        ch_df = pd.read_csv('call_history.csv')
        ch_df['Phone Number'] = ch_df['Phone Number'].apply(standardize_phone_number)
        ch_df['Call Timestamp'] = pd.to_datetime(ch_df['Call Timestamp'])
        
        # Insert Call History data
        ch_records = []
        for _, row in ch_df.iterrows():
            phone = row['Phone Number']
            ch_records.append((
                phone,
                row['Call Timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                row.get('Call Type', 'Unknown'),
                row.get('Service', 'Unknown'),
                'call_history',
                contact_dict.get(phone, '')
            ))
        
        # Read iTunes Calls CSV
        it_df = pd.read_csv('itunes-calls.csv')
        it_df['Phone Number'] = it_df['Phone Number'].apply(standardize_phone_number)
        it_df['Timestamp'] = pd.to_datetime(it_df['Timestamp'])
        
        # Insert iTunes data
        it_records = []
        for _, row in it_df.iterrows():
            phone = row['Phone Number']
            it_records.append((
                phone,
                row['Timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                row.get('Call Type', 'Unknown'),
                row.get('Service', 'Unknown'),
                'itunes',
                contact_dict.get(phone, '')
            ))
        
        # Batch insert records
        cursor.executemany(
            'INSERT INTO call_history (phone_number, timestamp, call_type, service, source, contact_name) VALUES (?, ?, ?, ?, ?, ?)',
            ch_records + it_records
        )
        
        # Create views for convenience
        cursor.execute('''
        CREATE VIEW IF NOT EXISTS call_summary AS
        SELECT 
            phone_number,
            MAX(contact_name) as contact_name,
            COUNT(CASE WHEN source = 'call_history' THEN 1 END) as call_history_count,
            COUNT(CASE WHEN source = 'itunes' THEN 1 END) as itunes_count,
            ABS(COUNT(CASE WHEN source = 'call_history' THEN 1 END) - 
                COUNT(CASE WHEN source = 'itunes' THEN 1 END)) as difference
        FROM call_history
        GROUP BY phone_number
        ''')
        
        # Commit changes
        conn.commit()
        print("Database created successfully!")
        
    except Exception as e:
        print(f"Error creating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    create_database() 