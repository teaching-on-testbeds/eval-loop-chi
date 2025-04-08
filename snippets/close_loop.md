

::: {.cell .markdown}

## Practice "closing the feedback loop"

When there are no natural ground truth labels, we need to explicitly "close the feedback loop":

* in order to evaluate how well our model does in production, versus in offline evaluation on a held-out test set,
* and also to get new "production data" on which to re-train the model when its performance degrades.

For example, with this food type classifier, once it is deployed to "real" users:

* We could set aside a portion of production data for a human to label. 
* We could set aside samples where the model has low confidence in its prediction, for a human to label. These extra-difficult samples are especially useful for re-training.
* We could allow users to give explicit feedback about whether the label assigned to their image is correct or not. This feedback may be sparse (some users won't bother giving feedback even if the label is wrong) and noisy (some users may give incorrect feedback). We can get human annotators to label this data, too.
* We could allow users to explicitly label their images, by changing the label that is assigned by the classifier. This feedback may be sparse (some users won't bother giving feedback even if the label is wrong) and noisy (some users may give incorrect feedback).

We're going to try out all of these options!
:::

::: {.cell .markdown}
### System Architecture and Data Flow

Here's how all the components work together:

1. **Flask Service**: This is our web application that users interact with. It uploads images to MinIO and creates task JSON files.

2. **FastAPI Service**: This provides the machine learning prediction endpoint that the Flask app calls.

3. **MinIO Object Store**: This stores all our data:
   - Images are stored in the "production" bucket by class
   - JSON task files are stored in the "labelstudio/tasks/" directory
   - Labeled data will be stored in output locations configured in Label Studio

4. **Label Studio**: This is our annotation platform that:
   - Reads task JSON files from the "labelstudio/tasks/" directory in MinIO
   - Presents images to annotators
   - Saves completed annotations to output storage locations "labelstudio/output/" in MinIO

Data flows like this:
User → Flask → FastAPI → Flask → MinIO Source Storage Buckets → Label Studio → Annotated Data Buckets (Target Storage Buckets)

Now, lets bring the system up by running the below cell!
:::

::: {.cell .code}
```python
# Bringing up system using Docker-compose
remote.run('docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml up -d')

# Lets wait 30 seconds for it to get ready
remote.run('sleep 15')
```
:::

::: {.cell .markdown}
Post that, let's run the script that sets up the necessary things in Label Studio 
1. Creates three different projects for each specific task ( Random sampling, User Feedback, Low Confidence) with necessary details.
2. Sets up the labeling interface with the same configuration for all projects
3. Connects to MinIO S3 storage for both input (source) and output (target) data
3. Configures separate folders for each project's data

After running the next cell, go to {node-public-ip}:8080 and login with credentials and explore Label Studio.
`username` : gourmetgramuser@gmail.com
`password` : gourmetgrampassword
:::

::: {.cell .markdown}

::: {.cell .code}
```python
# Setting up Label Studio (Replace label_studio_container_id with the correct container id using docker ps )
remote.run('docker exec label_studio_container_id python3 setup_label_studio.py')
```
:::

### Set aside data for a human to label

We are going to store the production images in a `production` bucket present in the minio object store. 

In order to do this, let's modify the flask application. 

1) Install s3fs package which we will use to interact with the Minio container 
```bash
pip install s3fs
```

2) Use nano to modify app.py and insert the following 3 blocks of code 

```python
import s3fs
import json
import datetime
import uuid
#Include jsonify here
from flask import Flask, redirect, url_for, request, render_template, jsonify
# Initalize s3fs 
fs = s3fs.S3FileSystem(endpoint_url="http://minio:9000",key="minioadmin",secret="minioadmin",use_ssl=False)

classes = np.array(["Bread", "Dairy product", "Dessert", "Egg", "Fried food",
    "Meat", "Noodles/Pasta", "Rice", "Seafood", "Soup",
    "Vegetable/Fruit"])

# Dictionary to track predictions
current_predictions = {}
```

```python
# Function to store prediction data
def store_prediction_in_tracking(prediction_data):
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
```

Change the predict function to this
```python
@app.route('/predict', methods=['GET', 'POST'])
def upload():
    preds = None
    if request.method == 'POST':
        f = request.files['file']
        filename = secure_filename(f.filename)
        f.save(os.path.join(app.instance_path, 'uploads', filename))
        img_path = os.path.join(app.instance_path, 'uploads', filename)
       
        preds, probs = request_fastapi(img_path)
        if preds:
            pred_index = np.where(classes == preds)[0][0]
            
            # Format the class directory name with the index
            class_dir = f"class_{pred_index:02d}"
            
            # Create the S3 path
            bucket_name = "production"
            s3_path = f"{bucket_name}/{class_dir}/{secure_filename(f.filename)}"
            
            # Upload the file to S3/MinIO
            fs.put(img_path, s3_path)

            prediction_id = str(uuid.uuid4())

            current_predictions[prediction_id] = {
                "prediction_id": prediction_id,
                "filename": filename,
                "prediction": preds,
                "confidence": probs,
                "image_url": f"http://localhost:9000/production/{class_dir}/{filename}",
                "class_dir": class_dir,
                "sampled" : False
            }

            # Store prediction in tracking
            store_prediction_in_tracking(current_predictions[prediction_id])
            
            return f'<button type="button" class="btn btn-info btn-sm">{preds}</button>'
    
    return '<a href="#" class="badge badge-warning">Warning</a>'
```

Execute the below cell to reload the Flask application with our new code. Now, every image that is predicted by the Flask application is stored in the `production` bucket in the respective class folder. You can test it by predicting an image and checking it in the Minio Object Store at {node-public-ip}:9001

:::

::: {.cell .code}
```python
# Restarting the Flask container with the updated frontend and app.py
remote.run("docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml restart flask")
```
:::

::: {.cell .code}
```python
# Set up a cron job to run random sampling once per day
remote.run("echo '0 0 * * * docker exec label-studio python3 /label-studio/random_sampling.py' | crontab -")
```
:::

::: {.cell .markdown}   

### Set aside samples for which model has low confidence

Low confidence means the model is unsure about the classification for a given image. These images which the model found difficult to predict are especially useful for re-training. 

Lets modify our Flask application so that the low confidence images are sent to human annotators for review and the annotated images are used for retraining later on.

1. Now, we define a new function `create_low_confidence_task` that creates a task for low confidence images in Label Studio and a dictionary `current_predictions` to keep track of prediction

```python

def create_low_confidence_task(image_url, predicted_class, confidence, filename):
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
    object_path = f"labelstudio/tasks/lowconfidence/task_{task_id}.json"
   
    # Upload JSON using s3fs
    with fs.open(object_path, 'w') as f:
        f.write(task_json)
   
    return task_id
```

2. We will call this function when the confidence of predicted image goes below a pre-defined threshold 

```python
@app.route('/predict', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        f = request.files['file']
        filename = secure_filename(f.filename)
        img_path = os.path.join(app.instance_path, 'uploads', filename)
        f.save(img_path)
       
        preds, probs = request_fastapi(img_path)
        if preds:
            pred_index = np.where(classes == preds)[0][0]
            
            # Format the class directory name with the index
            class_dir = f"class_{pred_index:02d}"
            
            # Create the S3 path
            bucket_name = "production"
            s3_path = f"{bucket_name}/{class_dir}/{filename}"
            
            # Upload the file to S3/MinIO
            fs.put(img_path, s3_path)

            prediction_id = str(uuid.uuid4())
            current_predictions[prediction_id] = {
                "prediction_id": prediction_id,
                "filename": filename,
                "prediction": preds,
                "confidence": probs,
                "image_url": f"http://localhost:9000/production/{class_dir}/{filename}",
                "class_dir": class_dir,
                "sampled" : False
            }

            store_prediction_in_tracking(current_predictions[prediction_id])

            confidence_threshold = 0.7

            if probs < confidence_threshold:
                create_low_confidence_task(
                    image_url=current_predictions[prediction_id]["image_url"],
                    predicted_class=preds,
                    confidence=probs,
                    filename=filename
                )
            
            return f'<button type="button" class="btn btn-info btn-sm">{preds}</button>'
    
    return '<a href="#" class="badge badge-warning">Warning</a>'
```

:::

::: {.cell .code}
```python
# Restarting the Flask container with the updated app.py
remote.run("docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml restart flask")
```
:::

::: {.cell .code}
```python
# Setting up a job to process the low confidence input jsons into Label Studio (Replace placeholder label-studio with actual container ID)
remote.run("(crontab -l 2>/dev/null; echo '0 * * * * docker exec label-studio python3 /label-studio/sync_script.py 1') | crontab -")
```
:::

::: {.cell .markdown}

### Get explicit feedback from users

Now, lets look towards the user whether they think the prediction given is correct or not. This feedback may be sparse (some users won't bother giving feedback even if the label is wrong) and noisy (some users may give incorrect feedback). We can get human annotators to label this data, too.

1. Just like the previous stage, we will include a new function create_user_feedback_task which creates tasks in Label Studio based on negative user feedback 

```python
def create_user_feedback_task(image_url, predicted_class, confidence, filename):
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
    object_path = f"labelstudio/tasks/userfeedback/task_{task_id}.json"
   
    # Upload JSON using s3fs
    with fs.open(object_path, 'w') as f:
        f.write(task_json)
   
    return task_id
```

2. We will update the predict function to include a feedback button in the response 
```python
@app.route('/predict', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        f = request.files['file']
        filename = secure_filename(f.filename)
        img_path = os.path.join(app.instance_path, 'uploads', filename)
        f.save(img_path)
       
        preds, probs = request_fastapi(img_path)
        if preds:
            pred_index = np.where(classes == preds)[0][0]
            
            # Format the class directory name with the index
            class_dir = f"class_{pred_index:02d}"
            
            # Create the S3 path
            bucket_name = "production"
            s3_path = f"{bucket_name}/{class_dir}/{filename}"
            
            # Upload the file to S3/MinIO
            fs.put(img_path, s3_path)

            # Store this prediction for feedback
            prediction_id = str(uuid.uuid4())
            current_predictions[prediction_id] = {
                "prediction_id": prediction_id,
                "filename": filename,
                "prediction": preds,
                "confidence": probs,
                "image_url": f"http://localhost:9000/production/{class_dir}/{filename}",
                "class_dir": class_dir,
                "sampled" : False
            }

            store_prediction_in_tracking(current_predictions[prediction_id])
            
            # Return the result with a flag icon for incorrect label feedback
            result_html = f'''
            <div style="display: flex; align-items: center; margin-top: 10px;">
                <button type="button" class="btn btn-info btn-sm">{preds}</button>
                <button class="btn btn-sm feedback-btn" data-prediction-id="{prediction_id}" 
                        data-bs-toggle="tooltip" data-bs-placement="top" title="Flag incorrect label"
                        style="background: none; border: none; color: #dc3545; padding: 2px 0 0 8px; margin-left: 5px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-flag" viewBox="0 0 16 16">
                        <path d="M14.778.085A.5.5 0 0 1 15 .5V8a.5.5 0 0 1-.314.464L14.5 8l.186.464-.003.001-.006.003-.023.009a12.435 12.435 0 0 1-.397.15c-.264.095-.631.223-1.047.35-.816.252-1.879.523-2.71.523-.847 0-1.548-.28-2.158-.525l-.028-.01C7.68 8.71 7.14 8.5 6.5 8.5c-.7 0-1.638.23-2.437.477A19.626 19.626 0 0 0 3 9.342V15.5a.5.5 0 0 1-1 0V.5a.5.5 0 0 1 1 0v.282c.226-.079.496-.17.79-.26C4.606.272 5.67 0 6.5 0c.84 0 1.524.277 2.121.519l.043.018C9.286.788 9.828 1 10.5 1c.7 0 1.638-.23 2.437-.477a19.587 19.587 0 0 0 1.349-.476l.019-.007.004-.002h.001"/>
                    </svg>
                </button>
            </div>
            '''
            
            return result_html
    
    return '<a href="#" class="badge badge-warning">Warning</a>'
```

3. A /feedback endpoint and respective feedback function that handles user feedback 
```python
@app.route('/feedback', methods=['POST'])
def feedback():
    """Handle user feedback about predictions"""
    data = request.json
    prediction_id = data.get('prediction_id')
    
    # Get the prediction data
    pred_data = current_predictions[prediction_id]
    
    # Create user feedback task
    task_id = create_user_feedback_task(
        image_url=pred_data["image_url"],
        predicted_class=pred_data["prediction"],
        confidence=pred_data["confidence"],
        filename=pred_data["filename"]
    )
    
    # Return response
    return jsonify({
        "success": True,
        "message": "Thank you for your feedback!"
    })
```
:::

::: {.cell .code}
```python
# Copying front end files into our flask container to update the UI to include feedback
remote.run("docker cp /home/cc/eval-loop-chi/frontend/feedback_v1/templates/index.html flask:/app/templates/index.html")
remote.run("docker cp /home/cc/eval-loop-chi/frontend/feedback_v1/templates/base.html flask:/app/templates/base.html")

remote.run("docker cp /home/cc/eval-loop-chi/frontend/feedback_v1/static/js/main.js flask:/app/static/js/main.js")
remote.run("docker cp /home/cc/eval-loop-chi/frontend/feedback_v1/static/css/main.css flask:/app/static/css/main.css")
```
:::

::: {.cell .code}
```python
# Restarting the Flask container with the updated frontend and app.py
remote.run("docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml restart flask")
```
:::

::: {.cell .code}
```python
# Setting up a job to process the low confidence input jsons into Label Studio (Replace placeholder with actual container ID)
remote.run("(crontab -l 2>/dev/null; echo '0 * * * * docker exec label-studio python3 /label-studio/sync_script.py 2') | crontab -")
```
:::

::: {.cell .markdown}
Now, go to the Flask frontend and you can see that the UI has a feedback button right of the prediction. Whenever user clicks on the Flag icon, a task json is sent to the input storage associated with 'User Feedback' Project. 
:::


### Get explicit labels from users

:::
