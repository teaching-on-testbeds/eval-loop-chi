

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
   - JSON output files are stored in the "labelstudio/tasks/" directory
   - Labeled data will be stored in output locations configured in Label Studio

4. **Label Studio**: This is our annotation platform that:
   - Reads task JSON files from the "labelstudio/tasks/" directory 
   - Presents images to annotators
   - Saves completed annotations to output storage locations "labelstudio/output/" in MinIO

Data flows like this:

`User → Flask → FastAPI → Flask → Source Storage (labelstudio/tasks/) → Label Studio → Target Storage (labelstudio/output/)`

:::

::: {.cell .markdown}
### Setting Up Label Studio for Annotation

Let's set up Label Studio, our tool for managing human annotations of images. 

Inside the SSH session,

First, find your Label Studio container ID:

```bash
docker ps | grep label
```

Run the below command : 
```bash
# Setting up Label Studio (Replace label_studio_container_id with the correct container id using docker ps )
docker exec <label_studio_container_id> python3 setup_label_studio.py
```

This script:

- Creates three projects (Random Sampling, Low Confidence, User Feedback)
- Configures the labeling interface for food classification
- Connects to MinIO for source and target storage
- Sets up separate directories for each project's data


Access Label Studio UI: Visit http://{node-public-ip}:8080 and login with

- Username: gourmetgramuser@gmail.com
- Password: gourmetgrampassword
- Go into each project and check the sample task created
- Go into project settings 
    - Check the Labelling interface tab
    - Check the Cloud Storage tab to see how the project connects to Source Storage and Target Storage
:::

::: {.cell .markdown}

### Set aside data for a human to label

We are going to store the images user provide in the `Production` bucket in MinIO Object store.

In order to do this, let's modify the flask application. 

Inside the SSH session : 

1) Add `s3fs` to requirements.txt in the gourmetgram folder

```bash
nano /home/cc/eval-loop-chi/gourmetgram/requirements.txt
```

2) Copy functions folder into gourmetgram folder

```bash
cp -r /home/cc/eval-loop-chi/functions /home/cc/eval-loop-chi/gourmetgram/functions
```

2) Modify the contents of app.py in gourmetgram folder using below command.

```bash
nano /home/cc/eval-loop-chi/gourmetgram/app.py
```

In app.py, 

Add these imports at the top of the file:

```python
import s3fs
import json
import datetime
import uuid
#Include jsonify here
from flask import Flask, redirect, url_for, request, render_template, jsonify
from functions.storage import store_prediction_in_tracking
```

Initialize S3 Filesystem and a dictionary to store predictions: 

```python
# Initalize s3fs 
fs = s3fs.S3FileSystem(endpoint_url="http://minio:9000",key="minioadmin",secret="minioadmin",use_ssl=False)

classes = np.array(["Bread", "Dairy product", "Dessert", "Egg", "Fried food",
    "Meat", "Noodles/Pasta", "Rice", "Seafood", "Soup",
    "Vegetable/Fruit"])

# Dictionary to store predictions
current_predictions = {}
```

Update the upload() function to save images and prediction details :

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
            store_prediction_in_tracking(fs, current_predictions[prediction_id])
            
            return f'<button type="button" class="btn btn-info btn-sm">{preds}</button>'
    
    return '<a href="#" class="badge badge-warning">Warning</a>'
```

Rebuild the Flask Container:

```bash
# Rebuild the Flask container with the updated app.py
docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml up flask --build
```

Our first feedback loop method randomly selects production images for human annotation. Let's set up a hourly cron job for random sampling and run it on demand once:

```bash
# Set up a cron job to run random sampling once a day
echo '0 0 * * * docker exec <label_studio_container_id> python3 /label-studio/random_sampling.py' | crontab -
```

```bash
docker exec <label_studio_container_id> python3 /label-studio/random_sampling.py' | crontab -
```

This cron job:

- Runs once per day
- Randomly selects unsampled images from the production bucket
- Creates task JSONs in the "labelstudio/tasks/randomsampling" folder

Set up an daily cron job to sync with Label Studio and run it on demand once:

```bash
(crontab -l 2>/dev/null; echo '0 0 * * * docker exec <label_studio_container_id> python3 /label-studio/sync_script.py 1') | crontab -
```

```bash
docker exec <label_studio_container_id> python3 /label-studio/sync_script.py 1
```

#### Testing the Feedback Loop

1. Go to http://{public-node-ip}:5000
2. Upload food-11 images images present in /data/food11 folder 
3. Wait for random sampling script to run and Label Studio to Sync and Go to http://{public-node-ip}:8080 and login to see the tasks created by random sampling. 
4. Complete the random sampling tasks and provide your prediction for the image.

:::

::: {.cell .markdown}   

### Set aside samples for which model has low confidence

Our second method identifies images where the model has low confidence in its prediction, making them valuable for retraining.

Use the below command to modify app.py :

```bash
nano /home/cc/eval-loop-chi/gourmetgram/app.py
```

1. Import Task Creation Function for low confidence tasks

Add this import to app.py:

```python
from functions.feedback_tasks import create_low_confidence_task
```

2. Update the upload() function in app.py to identify and send low confidence predictions for review based on a predefined threshold:

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

            store_prediction_in_tracking(fs, current_predictions[prediction_id])

            confidence_threshold = 0.7

            if probs < confidence_threshold:
                create_low_confidence_task(
                    fs,
                    image_url=current_predictions[prediction_id]["image_url"],
                    predicted_class=preds,
                    confidence=probs,
                    filename=filename
                )
            
            return f'<button type="button" class="btn btn-info btn-sm">{preds}</button>'
    
    return '<a href="#" class="badge badge-warning">Warning</a>'
```

3. Rebuild the Flask container
```bash
# Rebuild the Flask container with the updated app.py
docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml up flask --build
```

4. Setup hourly job to sync Label Studio and run it once on demand

```bash
# Setting up a job to process the low confidence input jsons into Label Studio (Replace placeholder label-studio with actual container ID)
(crontab -l 2>/dev/null; echo '0 * * * * docker exec <label_studio_container_id> python3 /label-studio/sync_script.py 2') | crontab -
```

```bash
docker exec <label_studio_container_id> python3 /label-studio/sync_script.py 2
```

#### Testing the Feedback Loop

1. Go to http://{public-node-ip}:5000.
2. Upload ambiguous images images present in /lowconfidence folder in data.
3. Wait for Label Studio to Sync and Go to http://{public-node-ip}:8080 and login to see the tasks created by low confidence predictions.
4. Complete the low confidence tasks by giving your prediction for the image.

:::


::: {.cell .markdown}

### Get explicit feedback from users

Our third method enables users to provide feedback when they think the model's prediction is incorrect. This feedback may be sparse (some users won't bother giving feedback even if the label is wrong) and noisy (some users may give incorrect feedback). We can get human annotators to label this data, too.

Use the below command to modify app.py :

```bash
nano /home/cc/eval-loop-chi/gourmetgram/app.py
```

1. Import Task Creation Function for user feedback tasks and add the flag icon SVG

```python
from functions.feedback_tasks import create_user_feedback_task

```

2. Update Upload Function to Include Feedback Button

```python
with open('./images/flag-icon.svg', 'r') as f:
    FLAG_SVG = f.read()

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

            store_prediction_in_tracking(fs,current_predictions[prediction_id])
            
            # Return the result with a flag icon for incorrect label feedback
            result_html = f'''
            <div style="display: flex; align-items: center; margin-top: 10px;">
                <button type="button" class="btn btn-info btn-sm">{preds}</button>
                <button class="btn btn-sm feedback-btn" data-prediction-id="{prediction_id}" 
                        data-bs-toggle="tooltip" data-bs-placement="top" title="Flag incorrect label"
                        style="background: none; border: none; color: #dc3545; padding: 2px 0 0 8px; margin-left: 5px;">
                    {FLAG_SVG}
                </button>
            </div>
            '''
            
            return result_html
    
    return '<a href="#" class="badge badge-warning">Warning</a>'
```

3. Add Feedback Route to Handle User Feedback

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
        fs,
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

4. Update Frontend Files and rebuild the Flask container 

```bash
# Copying front end files into our flask container to update the UI to include feedback
cp /home/cc/eval-loop-chi/frontend/feedback_v1/templates/index.html /home/cc/eval-loop-chi/gourmetgram/templates/index.html
cp /home/cc/eval-loop-chi/frontend/feedback_v1/templates/base.html /home/cc/eval-loop-chi/gourmetgram/templates/base.html

cp /home/cc/eval-loop-chi/frontend/feedback_v1/static/js/main.js /home/cc/eval-loop-chi/gourmetgram/static/js/main.js
cp /home/cc/eval-loop-chi/frontend/feedback_v1/static/css/main.css /home/cc/eval-loop-chi/gourmetgram/static/css/main.css

mkdir -p /home/cc/eval-loop-chi/gourmetgram/images/
cp /home/cc/eval-loop-chi/images/flag-icon.svg /home/cc/eval-loop-chi/gourmetgram/images
```

```bash
docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml up flask --build
```

5. Set up Label Studio Sync CRON Job for User feedback and run it once on demand

```bash
(crontab -l 2>/dev/null; echo '0 * * * * docker exec <label_studio_container_id> python3 /label-studio/sync_script.py 3') | crontab -
```

```bash
docker exec <label_studio_container_id> python3 /label-studio/sync_script.py 3
```

#### Testing the Feedback Loop

1. Go to http://{public-node-ip}:5000.
2. Upload  images present in data/userfeedback/ folder.
3. Provide negative feedback for the prediction
3. Wait for Label Studio to Sync and go to http://{public-node-ip}:8080 and login to see the tasks created by user feedback tasks. Complete the user feedback tasks.
:::

::: {.cell .markdown}
Now that we've collected labeled data from human annotators in Label Studio, we need to process these annotations and organize them for model retraining. The labeled data is currently stored in the /labelstudio/output/ path in our MinIO storage system.

Make sure you've finished the tasks in the Label Studio. To process these annotations and create organized training data, run:

```bash
docker exec <label_studio_container_id> python3 /label-studio/sync_script.py 
docker exec <label_studio_container_id> python3 /label-studio/process_outputs.py
```

This does the following:

- Synchronizes results by sending output tasks to the respective folders in `labelstudio` bucket
- Extracts the human-verified labels from the annotation results
- Retrieves the corresponding images from our production storage
- Organizes these images into class-specific buckets based on their corrected labels
- Creates a structured dataset ready for model retraining

:::

::: {.cell .markdown}
### Get explicit labels from users

Our last method is to allow users to explicitly label their images, by changing the label that is assigned by the classifier. This feedback may be sparse (some users won't bother giving feedback even if the label is wrong) and noisy (some users may give incorrect feedback).

Use the below command to modify app.py :

```bash
nano /home/cc/eval-loop-chi/gourmetgram/app.py
```
2. Add to imports at the top of the file : 

```python
from functions.feedback_tasks import create_output_json

PREDICTION_TEMPLATE_PATH = os.path.join('static', 'templates', 'prediction-result.html')
```

3. Update Upload Function and create a new route `/api/classes` that returns list of classes to the frontend: 

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
                "sampled": False
            }

            store_prediction_in_tracking(fs, current_predictions[prediction_id])
            
            # Return the result with a dropdown label and pencil icon
            template = open(PREDICTION_TEMPLATE_PATH).read()
            
            result_html = template.replace("{prediction_id}", prediction_id).replace("{prediction}", preds)
            
            return result_html
    
    return '<a href="#" class="badge badge-warning">Warning</a>'

@app.route('/api/classes', methods=['GET'])
def get_classes():
    """Return all available classes as JSON"""
    return jsonify(classes.tolist())
```

3. Update feedback function : 

```python
@app.route('/feedback', methods=['POST'])
def feedback():
    """Handle user feedback about predictions"""
    data = request.json
    prediction_id = data.get('prediction_id')
    corrected_class = data.get('corrected_class')
    
    if not prediction_id or not corrected_class:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    # Get the prediction data
    pred_data = current_predictions.get(prediction_id)
    
    if not pred_data:
        return jsonify({
            "success": False,
            "message": "Prediction not found!"
        }), 404
    
    if pred_data["prediction"] == corrected_class:
        return jsonify({
            "success": True,
            "message": "No changes needed - class already correct"
        })
    
    try:
        
        output_json_path = create_output_json(
            fs,
            image_url=pred_data["image_url"],
            predicted_class=pred_data["prediction"],
            corrected_class=corrected_class,
            filename=pred_data["filename"]
        )
        

        current_predictions[prediction_id]["prediction"] = corrected_class
        
        # Calculate the new class directory
        new_class_index = np.where(classes == corrected_class)[0][0]
        new_class_dir = f"class_{new_class_index:02d}"
        current_predictions[prediction_id]["class_dir"] = new_class_dir
        
        # Return response
        return jsonify({
            "success": True,
            "message": "Class updated successfully!",
            "output_json_path": output_json_path
        })
        
    except Exception as e:
        print(f"Error processing feedback: {e}")
        return jsonify({
            "success": False,
            "message": f"Error processing feedback: {str(e)}"
        }), 500
```

4. Update Frontend files and rebuild flask container : 

```bash
# Copying front end files into our flask container to update the UI to include feedback
cp /home/cc/eval-loop-chi/frontend/feedback_v2/templates/index.html /home/cc/eval-loop-chi/gourmetgram/templates/index.html
cp /home/cc/eval-loop-chi/frontend/feedback_v2/templates/base.html /home/cc/eval-loop-chi/gourmetgram/templates/base.html

cp /home/cc/eval-loop-chi/frontend/feedback_v2/static/js/main.js /home/cc/eval-loop-chi/gourmetgram/static/js/main.js
cp /home/cc/eval-loop-chi/frontend/feedback_v2/static/js/class-feedback.js /home/cc/eval-loop-chi/gourmetgram/static/js/class-feedback.js
cp /home/cc/eval-loop-chi/frontend/feedback_v2/static/css/main.css /home/cc/eval-loop-chi/gourmetgram/static/css/main.css

mkdir -p /home/cc/eval-loop-chi/gourmetgram/static/templates/
cp /home/cc/eval-loop-chi/frontend/feedback_v2/static/templates/prediction-result.html /home/cc/eval-loop-chi/gourmetgram/static/templates/prediction-result.html

```

```bash
docker-compose -f /home/cc/eval-loop-chi/docker/docker-compose-feedback.yaml up flask --build
```

#### Testing the Feedback Loop

1. Go to http://{public-node-ip}:5000.
2. Upload  images present in data/userfeedback/ folder.
3. Click the pencil icon and change the predicted class 
4. Run `docker exec <label_studio_container_id> python3 /label-studio/process_outputs.py` in SSH terminal in order to send the images to the correct class folder in `userfeedback2` bucket

:::
