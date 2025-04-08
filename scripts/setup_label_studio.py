#!/usr/bin/env python3
import requests
import time
import json
import os

# Configuration
LABEL_STUDIO_URL = os.environ.get('LABEL_STUDIO_URL', 'http://label-studio:8080')
API_TOKEN = os.environ.get('LABEL_STUDIO_USER_TOKEN', 'ab9927067c51ff279d340d7321e4890dc2841c4a')
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'http://minio:9000')
MINIO_USER = os.environ.get('MINIO_ROOT_USER', 'minioadmin')
MINIO_PASSWORD = os.environ.get('MINIO_ROOT_PASSWORD', 'minioadmin')

# Project configurations
PROJECTS = [
    {
        "title": "Random Sampling Review",
        "description": "Review and correct random sampled food classification predictions",
        "source_folder": "randomsampled",
        "target_folder": "randomsampled"
    },
    {
        "title": "Low Confidence Review",
        "description": "Review and correct low confidence food classification predictions",
        "source_folder": "lowconfidence",
        "target_folder": "lowconfidence"
    },
    {
        "title": "User Feedback Review",
        "description": "Review and correct food classification based on user feedback",
        "source_folder": "userfeedback",
        "target_folder": "userfeedback"
    }
]


headers = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json"
    }

# Label Studio labeling configuration XML
LABEL_CONFIG = '''
<View>
  <Image name="image" value="$image"/>
  <Header value="ML Prediction Review"/>
  
  <!-- Original ML Prediction (read-only display) -->
  <View className="prediction-info">
    <Header value="Original ML Prediction"/>
    <Text name="ml_prediction" value="$ml_prediction"/>
    <Text name="confidence" value="$confidence"/>
    <Text name="source" value="Source: $source"/>
  </View>
  
  <!-- Human Verification/Correction -->
  <Header value="Verify or Correct Classification"/>
  <Choices name="food_type" toName="image" choice="single" showInLine="true">
    <Choice value="Bread"/>
    <Choice value="Dairy product"/>
    <Choice value="Dessert"/>
    <Choice value="Egg"/>
    <Choice value="Fried food"/>
    <Choice value="Meat"/>
    <Choice value="Noodles/Pasta"/>
    <Choice value="Rice"/>
    <Choice value="Seafood"/>
    <Choice value="Soup"/>
    <Choice value="Vegetable/Fruit"/>
  </Choices>
  
  <!-- Optional: Add feedback field -->
  <TextArea name="notes" toName="image" placeholder="Optional: Add any notes about this classification" maxSubmissions="1"/>
</View>
'''

def wait_for_label_studio():
    """Wait for Label Studio to become available"""
    max_retries = 30
    retry_interval = 5
    
    print("Waiting for Label Studio to become available...")
    
    for attempt in range(max_retries):
        response = requests.get(f"{LABEL_STUDIO_URL}/health")
        if response.status_code == 200:
            print("Label Studio is up and running!")
            return True
        else:
            print(f"Label Studio not ready yet. Status code: {response.status_code}")
    
    print("Failed to connect to Label Studio after multiple attempts.")
    return False

def create_project(project_config):
    """Create a new Label Studio project"""
    
    project_data = {
        "title": project_config["title"],
        "description": project_config["description"],
        "label_config": LABEL_CONFIG
    }
    
    response = requests.post(
        f"{LABEL_STUDIO_URL}/api/projects",
        headers=headers,
        json=project_data
    )
    
    if response.status_code in [201, 200]:
        project = response.json()
        print(f"Created project '{project['title']}' with ID {project['id']}")
        return project
    else:
        print(f"Failed to create project: {response.status_code} {response.text}")
        return None

def connect_s3_source_storage(project_id, folder_name):
    """Connect S3 source storage to a project"""
    
    storage_config = {
        "title": f"Source Storage - {folder_name}",
        "description": f"S3 storage for {folder_name} tasks",  
        "project": project_id,
        "bucket": "labelstudio",
        "prefix": f"tasks/{folder_name}/",
        "aws_access_key_id": MINIO_USER,
        "aws_secret_access_key": MINIO_PASSWORD,
        "region_name": "us-east-1",  
        "s3_endpoint": MINIO_ENDPOINT
    }
    
    # Create the storage connection
    response = requests.post(
        f"{LABEL_STUDIO_URL}/api/storages/s3",
        headers=headers,
        json=storage_config
    )
    
    if response.status_code in [201, 200]:
        storage = response.json()
        print(f"Connected source storage for folder '{folder_name}' to project {project_id}")
        
        # Sync storage immediately
        sync_response = requests.post(
            f"{LABEL_STUDIO_URL}/api/storages/s3/{storage['id']}/sync",
            headers=headers
        )
        
        if sync_response.status_code in [200, 201, 204]:
            print(f"Triggered sync for source storage")
        else:
            print(f"Failed to trigger sync: {sync_response.status_code} {sync_response.text}")
            
        return storage
    else:
        print(f"Failed to connect source storage: {response.status_code} {response.text}")
        return None

def connect_s3_target_storage(project_id, folder_name):
    """Connect S3 target storage to a project"""
    
    storage_config = {
        "title": f"Target Storage - {folder_name}",
        "description": f"S3 storage for exporting {folder_name} annotations",
        "project": project_id,
        "bucket": "labelstudio",
        "prefix": f"output/{folder_name}/",
        "can_delete_objects": True,
        "aws_access_key_id": MINIO_USER,
        "aws_secret_access_key": MINIO_PASSWORD,
        "region_name": "us-east-1", 
        "s3_endpoint": MINIO_ENDPOINT
    }
    
    response = requests.post(
        f"{LABEL_STUDIO_URL}/api/storages/export/s3",
        headers=headers,
        json=storage_config
    )
    
    if response.status_code in [201, 200]:
        storage = response.json()
        print(f"Connected target storage for folder '{folder_name}' to project {project_id}")
        return storage
    else:
        print(f"Failed to connect target storage: {response.status_code} {response.text}")
        return None

def setup_label_studio():
    """Set up Label Studio with projects and storage connections"""
    # Wait for Label Studio to be available
    if not wait_for_label_studio():
        return False
    
    # Check for existing projects
    headers = {"Authorization": f"Token {API_TOKEN}"}
    
    # Create projects and connect storages
    for project_config in PROJECTS:

        # Create new project
        project = create_project(project_config)
        if not project:
            continue
        project_id = project["id"]
        
        # Connect source storage
        source_storage = connect_s3_source_storage(project_id, project_config["source_folder"])
        
        # Connect target storage
        target_storage = connect_s3_target_storage(project_id, project_config["target_folder"])
        
    
    return True

if __name__ == "__main__":
    setup_label_studio()