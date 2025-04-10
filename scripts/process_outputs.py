#!/usr/bin/env python3
import json
import s3fs
import os
import datetime

# Initialize S3 filesystem with MinIO connection
fs = s3fs.S3FileSystem(
    endpoint_url="http://minio:9000",
    key="minioadmin",
    secret="minioadmin",
    use_ssl=False
)

def process_outputs():
    """
    Process Label Studio output JSONs and move images to appropriate buckets
    based on the annotator's classification.
    """
    # Dictionary mapping Label Studio project output directories to target buckets
    output_mappings = {
        "randomsampled": "cleanproduction",
        "lowconfidence": "lowconfidence", 
        "userfeedback": "userfeedback",
        "userfeedback2": "userfeedback2",
    }
    
    # Process each output directory
    for source_dir, target_bucket in output_mappings.items():
        # Get list of output JSON files from this directory
        output_path = f"labelstudio/output/{source_dir}/"
        if fs.exists(output_path):
            json_files = [f for f in fs.ls(output_path)]
            
            
            for json_file in json_files:
                # Read and parse the JSON file
                with fs.open(json_file, 'r') as f:
                    try:
                        annotation_data = json.load(f)
                        
                        # Extract original image URL
                        image_url = annotation_data.get('task', {}).get('data', {}).get('image', '')

                        # Extract the annotated result
                        results = annotation_data.get('result', [])

                        if results and image_url:
                            # Extract chosen class value (the annotator's choice)
                            for result in results:
                                if result.get('type') == 'choices':
                                    # Get the selected class
                                    chosen_value = result.get('value', {}).get('choices', [])[0]
                                    if chosen_value:
                                        # Extract the production path components
                                        filename = image_url.split('/')[-1]
                                        
                                        # Format the class directory based on new classification
                                        # Get class index from the chosen value (e.g., "Bread" = 0)
                                        classes = ["Bread", "Dairy product", "Dessert", "Egg", "Fried food",
                                                 "Meat", "Noodles/Pasta", "Rice", "Seafood", "Soup",
                                                 "Vegetable/Fruit"]
                                        try:
                                            class_index = classes.index(chosen_value)
                                            new_class_dir = f"class_{class_index:02d}"
                                            
                                            # Create path in target bucket if it doesn't exist
                                            target_dir = f"{target_bucket}/{new_class_dir}"
                                            if not fs.exists(target_dir):
                                                fs.makedirs(target_dir)
                                            
                                            # Source image path in production bucket
                                            source_image = image_url.replace('http://localhost:9000/', '')
                                            
                                            # Target path in appropriate bucket 
                                            target_path = f"{target_bucket}/{new_class_dir}/{filename}"
                                            
                                            # Copy the image
                                            fs.copy(source_image, target_path)
                                            
                                            fs.rm(json_file)
                                        except ValueError:
                                            # Class not found in list
                                            pass
                    except:
                        # Skip files with parsing issues
                        pass

if __name__ == "__main__":
    process_outputs()