import pandas as pd

def load_and_process_call_history(file_path):
    # Read call history CSV
    df = pd.read_csv(file_path)
    # Group by phone number and count occurrences
    call_counts = df.groupby('Phone Number')['Call Timestamp'].count().to_dict()
    return call_counts

def load_and_process_itunes_calls(file_path):
    # Read iTunes calls CSV
    df = pd.read_csv(file_path)
    # Get the Total Calls column directly
    call_counts = df.set_index('Phone Number')['Total Calls'].to_dict()
    return call_counts

def compare_call_counts():
    # Load data from both files
    call_history_counts = load_and_process_call_history('call_history.csv')
    itunes_counts = load_and_process_itunes_calls('itunes-calls.csv')
    
    # Get all unique phone numbers
    all_numbers = set(list(call_history_counts.keys()) + list(itunes_counts.keys()))
    
    # Compare counts
    print("\nCall Count Comparison:")
    print("-" * 80)
    print(f"{'Phone Number':<20} {'Call History':<15} {'iTunes':<15} {'Difference':<15}")
    print("-" * 80)
    
    for number in sorted(all_numbers):
        history_count = call_history_counts.get(number, 0)
        itunes_count = itunes_counts.get(number, 0)
        difference = abs(history_count - itunes_count)
        
        if history_count != itunes_count:
            print(f"{number:<20} {history_count:<15} {itunes_count:<15} {difference:<15}")

if __name__ == "__main__":
    compare_call_counts() 