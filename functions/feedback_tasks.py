import uuid
import json
import datetime
import s3fs

# Get the s3fs from the calling module
def create_low_confidence_task(fs, image_url, predicted_class, confidence, filename):
    # Create unique task ID
    task_id = str(uuid.uuid4())
   
    # Create task data
    task_data = {
        "data": {
            "image": image_url,
            "ml_prediction": predicted_class,
            "confidence": confidence,
            "user_feedback": "low_confidence",
            "source": "low_confidence",
            "timestamp": datetime.datetime.now().isoformat()
        }
    }
   
    # Create JSON file in memory
    task_json = json.dumps(task_data, indent=2)
   
    # Define the object path
    object_path = f"labelstudio/tasks/lowconfidence/task{task_id}.json"
   
    # Upload JSON using s3fs
    with fs.open(object_path, 'w') as f:
        f.write(task_json)
   
    return task_id

def create_user_feedback_task(fs, image_url, predicted_class, confidence, filename):
    # Create unique task ID
    task_id = str(uuid.uuid4())
   
    # Create task data
    task_data = {
        "data": {
            "image": image_url,
            "ml_prediction": predicted_class,
            "confidence": confidence,
            "user_feedback": "incorrect",
            "source": "user_feedback",
            "timestamp": datetime.datetime.now().isoformat()
        }
    }
   
    # Create JSON file in memory
    task_json = json.dumps(task_data, indent=2)
   
    # Define the object path
    object_path = f"labelstudio/tasks/userfeedback/task{task_id}.json"
   
    # Upload JSON using s3fs
    with fs.open(object_path, 'w') as f:
        f.write(task_json)
   
    return task_id

def create_output_json(fs, image_url, predicted_class, corrected_class, filename):
    """Create JSON file for feedback in the output/userfeedback2 directory in the format expected by process_outputs.py"""
    # Create unique task ID
    task_id = str(uuid.uuid4())
   
    # Create data in the expected format
    feedback_data = {
        "task": {
            "data": {
                "image": image_url
            }
        },
        "result": [
            {
                "type": "choices",
                "value": {
                    "choices": [corrected_class]
                }
            }
        ]
    }
   
    # Create JSON file in memory
    task_json = json.dumps(feedback_data, indent=2)
   
    # Define the object path
    object_path = f"labelstudio/output/userfeedback2/feedback_{task_id}.json"
   
    # Upload JSON using s3fs
    with fs.open(object_path, 'w') as f:
        f.write(task_json)
   
    return object_path