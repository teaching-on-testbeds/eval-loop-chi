import datetime
import json
import s3fs

# Function to store predictions
def store_prediction_in_tracking(fs, prediction_data):
    # Path to the JSON file in tracking bucket
    object_path = "tracking/production.json"
    
    # Check if the file already exists
    try:
        if fs.exists(object_path):
            # Read existing data
            with fs.open(object_path, 'r') as f:
                existing_data = json.load(f)
        else:
            # Start with empty list if file doesn't exist
            existing_data = []
            
        # Add new prediction data with timestamp
        prediction_data["timestamp"] = datetime.datetime.now().isoformat()
        existing_data.append(prediction_data)
        
        # Write updated data back to file
        with fs.open(object_path, 'w') as f:
            json.dump(existing_data, f, indent=2)
            
    except Exception as e:
        print(f"Error storing prediction in tracking: {e}")