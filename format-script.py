import csv
from typing import List, Dict

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

def update_csv():
    # Read the existing CSV file
    rows = []
    with open('itunes-calls.csv', 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        headers = reader.fieldnames
        
        for row in reader:
            # Update phone number format
            row['Phone Number'] = standardize_phone_number(row['Phone Number'])
            rows.append(row)
    
    # Write back to the file with updated phone numbers
    with open('itunes-calls.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

if __name__ == '__main__':
    update_csv()
