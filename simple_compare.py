import csv
from datetime import datetime

def load_csv_log(filename):
    calls = {}
    with open(filename, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        for row in reader:
            if not row:  # Skip empty rows
                continue
            try:
                timestamp = row[4]
                phone = row[1]
                key = (phone, timestamp)
                calls[key] = {
                    'phone': phone,
                    'timestamp': timestamp,
                    'type': row[6],
                    'area_code': row[10]
                }
            except Exception as e:
                print(f"Error processing row: {row}")
                print(f"Error: {str(e)}")
                continue
    return calls

# Load both logs
print("Loading call_history.csv...")
csv_log = load_csv_log('call_history.csv')

# Print summary
print("\nCall Log Analysis")
print("================")
print(f"Total calls in call_history.csv: {len(csv_log)}")

# Analyze call patterns
number_counts = {}
area_code_counts = {}
call_type_counts = {}
calls_by_hour = {}

for key, call in csv_log.items():
    # Count calls per number
    phone = call['phone']
    if phone not in number_counts:
        number_counts[phone] = 0
    number_counts[phone] += 1
    
    # Count area codes
    area_code = call['area_code']
    if area_code not in area_code_counts:
        area_code_counts[area_code] = 0
    area_code_counts[area_code] += 1
    
    # Count call types
    call_type = call['type']
    if call_type not in call_type_counts:
        call_type_counts[call_type] = 0
    call_type_counts[call_type] += 1
    
    # Count calls by hour
    try:
        hour = datetime.strptime(call['timestamp'], '%Y-%m-%d %H:%M:%S').hour
        if hour not in calls_by_hour:
            calls_by_hour[hour] = 0
        calls_by_hour[hour] += 1
    except:
        pass

print("\nTop 10 most called numbers:")
for phone, count in sorted(number_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"- {phone}: {count} calls")

print("\nArea code distribution:")
for code, count in sorted(area_code_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"- {code}: {count} calls")

print("\nCall types:")
for type_name, count in call_type_counts.items():
    print(f"- {type_name}: {count} calls")

print("\nCalls by hour:")
for hour in sorted(calls_by_hour.keys()):
    print(f"{hour:02d}:00 - {calls_by_hour[hour]} calls") 