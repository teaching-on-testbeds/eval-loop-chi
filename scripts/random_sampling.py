#!/usr/bin/env python3
import os
import json
import random
import datetime
import uuid
from pathlib import Path

# Configuration 
MINIO_USER = os.environ.get('MINIO_ROOT_USER', 'minioadmin')
MINIO_PASSWORD = os.environ.get('MINIO_ROOT_PASSWORD', 'minioadmin')
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'http://minio:9000')
TRACKING_BUCKET = 'tracking'
PRODUCTION_DATA_FILE = f'{TRACKING_BUCKET}/production.json'  
SAMPLE_COUNT = int(os.environ.get('SAMPLE_COUNT', '5'))

# Import for S3 operations
import s3fs

# Initialize S3 filesystem
fs = s3fs.S3FileSystem(
    key=MINIO_USER,
    secret=MINIO_PASSWORD,
    client_kwargs={
        'endpoint_url': MINIO_ENDPOINT
    },
    use_ssl=False 
)

def get_unsampled_images():
    """Get images from production.json that have sampled=False"""
   
    # Read production data
    if not fs.exists(PRODUCTION_DATA_FILE):
        print(f"Production data file {PRODUCTION_DATA_FILE} does not exist")
        return []
        
    with fs.open(PRODUCTION_DATA_FILE, 'r') as f:
        production_data = json.load(f)
   
    # Filter for entries with sampled=False
    unsampled_images = [
        img for img in production_data
        if img.get('sampled') == False  # Using the sampled flag you added
    ]
   
    return unsampled_images, production_data

def mark_as_sampled(production_data, prediction_ids):
    """Mark selected predictions as sampled in the production data"""
    for pred in production_data:
        if pred.get('prediction_id') in prediction_ids:
            pred['sampled'] = True
    
    # Write back the updated production data
    with fs.open(PRODUCTION_DATA_FILE, 'w') as f:
        json.dump(production_data, f, indent=2)

def create_task_json(image_url, predicted_class, confidence, filename):
    """Create a task JSON file for Label Studio"""
   
    # Create a unique task ID
    task_id = str(uuid.uuid4())
   
    # Create task data structure
    task_data = {
        "data": {
            "image": image_url,
            "ml_prediction": predicted_class,
            "confidence": confidence,
            "user_feedback": "random_sample",
            "source": "random_sampling",
            "timestamp": datetime.datetime.now().isoformat()
        }
    }
   
    # Define the object path
    object_path = f"labelstudio/tasks/randomsampled/task_{task_id}.json"
   
    # Upload JSON using s3fs
    with fs.open(object_path, 'w') as f:
        f.write(json.dumps(task_data, indent=2))
   
    return task_id

def sample_random_images():
    """Sample random images from unsampled production data and create task JSONs"""
    # Get all unsampled images and complete production data
    unsampled_images, production_data = get_unsampled_images()
    
    if not unsampled_images:
        print("No unsampled images found in production data")
        return
   
    # Determine how many images to sample
    sample_size = min(SAMPLE_COUNT, len(unsampled_images))
    sampled_images = random.sample(unsampled_images, sample_size)
   
    print(f"Selected {sample_size} random images for sampling")
   
    # Track prediction IDs to mark as sampled
    prediction_ids = []
    
    # Process each sampled image
    for img in sampled_images:
        # Get data from production record
        image_url = img.get('image_url')
        predicted_class = img.get('prediction')
        confidence = img.get('confidence')
        filename = img.get('filename')
        prediction_id = img.get('prediction_id', str(uuid.uuid4()))  # Use existing ID or create one
        
        # Create task JSON file
        task_id = create_task_json(
            image_url=image_url,
            predicted_class=predicted_class,
            confidence=confidence,
            filename=filename
        )
        
        # Add to the list of prediction IDs to mark as sampled
        prediction_ids.append(prediction_id)
        
        print(f"Successfully created task JSON for: {filename}")
   
    # Mark the selected predictions as sampled in the production data
    mark_as_sampled(production_data, prediction_ids)
    
    print(f"Successfully created {len(sampled_images)} task JSONs and marked them as sampled")

if __name__ == "__main__":
    sample_random_images()