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