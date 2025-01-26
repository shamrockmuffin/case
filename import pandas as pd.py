import pandas as pd

# Read the CSV files with headers
call_history = pd.read_csv('call_history.csv')
itunes_calls = pd.read_csv('itunes-calls.csv')

# Ensure Phone Number is string type in both dataframes
call_history['Phone Number'] = call_history['Phone Number'].astype(str)
itunes_calls['Phone Number'] = itunes_calls['Phone Number'].astype(str)

# Convert timestamp strings to datetime objects
call_history['Call Timestamp'] = pd.to_datetime(call_history['Call Timestamp'])
itunes_calls['Timestamp'] = pd.to_datetime(itunes_calls['Timestamp'])

# Merge the two dataframes on Phone Number and Timestamp
merged = pd.merge(
    call_history,
    itunes_calls,
    left_on=['Phone Number', 'Call Timestamp'],
    right_on=['Phone Number', 'Timestamp'],
    how='outer',
    suffixes=('_ch', '_it')
)

# Identify rows with differences in call counts
merged['diff'] = (
    merged['Call Timestamp'].isna() |
    merged['Timestamp'].isna()
)

# Extract differences
differences = merged[merged['diff']].copy()

# Create a formatted timestamp column
differences['Formatted Timestamp'] = differences['Call Timestamp'].fillna(differences['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

# Group by Phone Number and aggregate the differences
diff_summary = differences.groupby('Phone Number').agg(
    difference_count=('Formatted Timestamp', 'count'),
    timestamps=('Formatted Timestamp', lambda x: ', '.join(x))
).reset_index()

# Print the results
print("\nSummary of Call Count Differences:")
print("-" * 80)
print(f"{'Phone Number':<15} {'Difference Count':<20} {'Timestamps':<45}")
print("-" * 80)

for _, row in diff_summary.iterrows():
    print(f"{row['Phone Number']:<15} {row['difference_count']:<20} {row['timestamps']:<45}")

print("-" * 80)
import tkinter as tk
from tkinter import scrolledtext

# Create a markdown string from the diff_summary dataframe
markdown_text = diff_summary.to_markdown()

# Initialize the Tkinter window
window = tk.Tk()
window.title("Call Count Differences")

# Create a scrolled text widget
text_area = scrolledtext.ScrolledText(window, wrap=tk.WORD, width=100, height=30)
text_area.pack(expand=True, fill='both')

# Insert the markdown text into the text widget
text_area.insert(tk.END, markdown_text)

# Make the text widget read-only
text_area.configure(state='disabled')

# Run the Tkinter event loop
window.mainloop()

