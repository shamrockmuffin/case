import pandas as pd

try:
    # Read the CSV file
    df = pd.read_csv('itunes-calls.csv')
    
    # Count total calls for each phone number
    phone_counts = df['Phone Number'].value_counts().to_dict()
    
    # Create new column list
    columns = list(df.columns)
    
    # Create new dataframe with reordered columns
    new_df = pd.DataFrame()
    new_df['Phone Number'] = df['Phone Number']
    new_df['Timestamp'] = df['Timestamp']
    new_df['Total Calls'] = df['Phone Number'].map(phone_counts)
    new_df['Call Type'] = df['Call Type']
    new_df['Service'] = df['Service']
    
    # Save the modified CSV
    new_df.to_csv('itunes-calls.csv', index=False)
    print("Successfully added Total Calls column")
except Exception as e:
    print(f"An error occurred: {str(e)}") 