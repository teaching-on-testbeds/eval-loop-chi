#!/usr/bin/env python3
import requests
import time
import os
import json
import argparse

# Configuration
LABEL_STUDIO_URL = os.environ.get('LABEL_STUDIO_URL', 'http://label-studio:8080')
API_TOKEN = os.environ.get('LABEL_STUDIO_USER_TOKEN', 'ab9927067c51ff279d340d7321e4890dc2841c4a')

# Map of project IDs to storage types
PROJECT_MAP = {
    "1": "randomsampled",
    "2": "lowconfidence",
    "3": "userfeedback"
}

def get_source_storage_id(project_id, storage_type):
    """Find the source storage ID for a project"""
    headers = {
        "Authorization": f"Token {API_TOKEN}"
    }
    
    response = requests.get(
        f"{LABEL_STUDIO_URL}/api/storages/s3?project={project_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        storages = response.json()
        for storage in storages:
            if f"Source Storage - {storage_type}" in storage["title"]:
                return storage["id"]
    
    return None

def sync_project_storage(project_id):
    """Sync the source storage for a specific project ID"""
    if project_id not in PROJECT_MAP:
        print(f"Unknown project ID: '{project_id}'")
        return False
        
    storage_type = PROJECT_MAP[project_id]
    print(f"Attempting to sync {storage_type} storage for project ID {project_id}...")
    
    # Get storage ID
    storage_id = get_source_storage_id(project_id, storage_type)
    if not storage_id:
        print(f"Source storage for {storage_type} not found in project {project_id}!")
        return False
    
    # Sync storage
    headers = {
        "Authorization": f"Token {API_TOKEN}"
    }
    
    sync_response = requests.post(
        f"{LABEL_STUDIO_URL}/api/storages/s3/{storage_id}/sync",
        headers=headers
    )
    
    if sync_response.status_code in [200, 201, 204]:
        print(f"Successfully synced {storage_type} storage for project ID {project_id}")
        return True
    else:
        print(f"Failed to sync {storage_type} storage: {sync_response.status_code} {sync_response.text}")
        return False

def main():
    """Main function to sync project storages"""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Sync Label Studio project source storages')
    parser.add_argument('project_ids', nargs='*', help='Project IDs to sync. If none provided, all projects will be synced.')
    
    args = parser.parse_args()
    
    # Determine which projects to sync
    project_ids_to_sync = args.project_ids
    if not project_ids_to_sync:
        # If no projects specified, sync all
        project_ids_to_sync = list(PROJECT_MAP.keys())
    
    print(f"Starting storage sync job for project IDs: {', '.join(project_ids_to_sync)}")
    
    # Wait a bit for Label Studio to be fully operational
    time.sleep(5)
    
    # Sync each project's storage
    for project_id in project_ids_to_sync:
        if project_id in PROJECT_MAP:
            sync_project_storage(project_id)
        else:
            print(f"Unknown project ID: '{project_id}'. Available project IDs: {', '.join(PROJECT_MAP.keys())}")
    
    print("Storage sync job completed!")

if __name__ == "__main__":
    main()