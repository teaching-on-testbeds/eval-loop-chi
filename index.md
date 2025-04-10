

<hr>

<small>Questions about this material? Contact Fraida Fund</small>

<hr>

<small>This material is based upon work supported by the National Science Foundation under Grant No. 2230079.</small>

<small>Any opinions, findings, and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect the views of the National Science Foundation.</small> - offline evaluation - stage. In this stage, it is evaluated using a held-out evaluation set not used in training, and potentially other special evaluation sets (as we'll see in this tutorial).
* **Staging**: Given satisfactory performance on the online evaluation, the model may be *packaged* as part of a service, and then this package promoted to a staging environment that mimics the "production" service but without live users. In this staging environmenmt, we can perform integration tests against the service and also load tests to evaluate the inference performance of the system.
* **Canary** (or blue/green, or other "preliminary" live environment): From the staging environment, the service can be promoted to a canary or other preliminary environment, where it gets requests from a small fraction of live users. In this environment, we are closely monitoring the service, its predictions, and the infrastructure for any signs of problems. We will try to "close the feedback loop" so that we can evaluate how effective our model is on production data, and potentially, evaluate the system on business metrics.
* **Production**: Finally, after a thorough offline and online evaluation, we may promote the model to the live production environment, where it serves most users. We will continue monitoring the system for signs of degradation or poor performance.

In this particular section, we will practice evaluation and monitoring in the *online* stage - when a system is serving some or all real users - and specifically the part where we "closed the feedback loop" in order to evaluate how well our system performs on production data.

![This tutorial focuses on the online testing stage.](images/stages-online.svg)

To run this experiment, you should have already created an account on Chameleon, and become part of a project. You should also have added your SSH key to the KVM@TACC site.



## Experiment resources 

For this experiment, we will provision one virtual machine on KVM@TACC.

Our initial online system, with monitoring of the live service, will include the following components:

* a FastAPI endpoint for our model
* a Flask app that sends requests to our FastAPI endpoint

These comprise the operational system we want to evaluate and monitor! To this, we'll add:

* Prometheus, an open source systems monitoring and alerting platform
* and Grafana, a dashboard platform that lets us visualize metrics collected by Prometheus

These will help us monitor operational metrics, like response time or number of requests per second.



## Open this experiment on Trovi


When you are ready to begin, you will continue with the next step, in which you bring up and configure a VM instance! To begin this step, open this experiment on Trovi:

* Use this link: [Evaluation of ML systems by closing the feedback loop](https://chameleoncloud.org/experiment/share/) on Trovi
* Then, click “Launch on Chameleon”. This will start a new Jupyter server for you, with the experiment materials already in it, including the notebok to bring up the VM instance.






## Launch and set up a VM instance- with python-chi

We will use the `python-chi` Python API to Chameleon to provision our VM server. 

We will execute the cells in this notebook inside the Chameleon Jupyter environment.

Run the following cell, and make sure the correct project is selected. 


```python
from chi import server, context
import chi, os, time, datetime

context.version = "1.0" 
context.choose_project()
context.choose_site(default="KVM@TACC")
```


We will use bring up a `m1.medium` flavor server with the `CC-Ubuntu24.04` disk image. 

> **Note**: the following cell brings up a server only if you don't already have one with the same name! (Regardless of its error state.) If you have a server in ERROR state already, delete it first in the Horizon GUI before you run this cell.



```python
username = os.getenv('USER') # all exp resources will have this prefix
s = server.Server(
    f"node-eval-loop-{username}", 
    image_name="CC-Ubuntu24.04",
    flavor_name="m1.medium"
)
s.submit(idempotent=True)
```



Then, we'll associate a floating IP with the instance:


```python
s.associate_floating_ip()
```

```python
s.refresh()
s.check_connectivity()
```


In the output below, make a note of the floating IP that has been assigned to your instance (in the "Addresses" row).


```python
s.refresh()
s.show(type="widget")
```


By default, all connections to VM resources are blocked, as a security measure.  We need to attach one or more "security groups" to our VM resource, to permit access over the Internet to specified ports.

The following security groups will be created (if they do not already exist in our project) and then added to our server:



```python
security_groups = [
  {'name': "allow-ssh", 'port': 22, 'description': "Enable SSH traffic on TCP port 22"},
  {'name': "allow-5000", 'port': 5000, 'description': "Enable TCP port 5000 (used by Flask)"},
  {'name': "allow-8000", 'port': 8000, 'description': "Enable TCP port 8000 (used by FastAPI)"},
  {'name': "allow-8888", 'port': 8888, 'description': "Enable TCP port 8888 (used by Jupyter)"},
  {'name': "allow-3000", 'port': 3000, 'description': "Enable TCP port 3000 (used by Grafana)"},
  {'name': "allow-9090", 'port': 9090, 'description': "Enable TCP port 9090 (used by Prometheus)"},
  {'name': "allow-8080", 'port': 8080, 'description': "Enable TCP port 8080 (used by cAdvisor, Label Studio)"}
]
```


```python
# configure openstacksdk for actions unsupported by python-chi
os_conn = chi.clients.connection()
nova_server = chi.nova().servers.get(s.id)

for sg in security_groups:

  if not os_conn.get_security_group(sg['name']):
      os_conn.create_security_group(sg['name'], sg['description'])
      os_conn.create_security_group_rule(sg['name'], port_range_min=sg['port'], port_range_max=sg['port'], protocol='tcp', remote_ip_prefix='0.0.0.0/0')

  nova_server.add_security_group(sg['name'])

print(f"updated security groups: {[group.name for group in nova_server.list_security_group()]}")
```







### Retrieve code and notebooks on the instance

Now, we can use `python-chi` to execute commands on the instance, to set it up. We'll start by retrieving the code and other materials on the instance.


```python
s.execute("git clone https://github.com/teaching-on-testbeds/eval-loop-chi")
s.execute("cd eval-loop-chi && git clone -b fastapi https://github.com/teaching-on-testbeds/gourmetgram.git")
```



### Set up Docker

Here, we will set up the container framework.


```python
s.execute("curl -sSL https://get.docker.com/ | sudo sh")
s.execute("sudo groupadd -f docker; sudo usermod -aG docker $USER")
```



## Open an SSH session

Finally, open an SSH sesson on your server. From your local terminal, run

```
ssh -i ~/.ssh/id_rsa_chameleon cc@A.B.C.D
```

where

* in place of `~/.ssh/id_rsa_chameleon`, substitute the path to your own key that you had uploaded to KVM@TACC
* in place of `A.B.C.D`, use the floating IP address you just associated to your instance.





## Prepare data

For the rest of this tutorial, we'll be evaluating models on the [Food-11 dataset](https://www.epfl.ch/labs/mmspg/downloads/food-image-datasets/). We're going to prepare a Docker volume with this dataset already prepared on it, so that the containers we create later can attach to this volume and access the data. 




First, create the volume:

```bash
# runs on node-eval
docker volume create food11
```

Then, to populate it with data, run

```bash
# runs on node-eval
docker compose -f serve-model-chi/docker/docker-compose-data.yaml up -d
```

This will run a temporary container that downloads the Food-11 dataset, organizes it in the volume, and then stops. It may take a minute or two. You can verify with 

```bash
# runs on node-eval
docker ps
```

that it is done - when there are no running containers.

Finally, verify that the data looks as it should. Start a shell in a temporary container with this volume attached, and `ls` the contents of the volume:

```bash
# runs on eval
docker run --rm -it -v food11:/mnt alpine ls -l /mnt/Food-11/
```

it should show "evaluation", "validation", and "training" subfolders.



## Launch containers

Inside the SSH session, bring up the Flask, FastAPI, LabelStudio, Scheduler & MinIO services:


```bash
# runs on node-eval-loop
docker compose -f eval-loop-chi/docker/docker-compose-feedback.yaml up -d
```

```bash
# Wait 30 seconds for system to get ready
sleep 30
```




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


### Setting Up Label Studio for Annotation

Let's set up Label Studio, our tool for managing human annotations of images. 

Inside the SSH session,

Run the below command : 
```bash
# Setting up Label Studio 
docker exec scheduler python3 /app/scripts/setup_label_studio.py
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


### Set aside data for a human to label

This stage involves storing user-submitted images in the `Production` bucket within our MinIO Object Store 

In order to do this, let's modify the flask application. 

Inside the SSH session : 

1) Add `s3fs` to requirements.txt in the gourmetgram folder

```bash
nano /home/cc/eval-loop-chi/gourmetgram/requirements.txt
```

2) Copy utils folder into gourmetgram folder

```bash
cp -r /home/cc/eval-loop-chi/gourmetgram_utils /home/cc/eval-loop-chi/gourmetgram/gourmetgram_utils
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
from gourmetgram_utils.storage import store_prediction_in_tracking
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

Our first feedback loop method randomly selects production images for human annotation.

Our scheduler container includes cron jobs for daily random sampling and Label Studio synchronization, automating our data collection and annotation workflow without requiring manual intervention. Let's take a look at it: 

```bash
docker exec scheduler crontab -l
```

This cron job:

- Runs once per day
- Randomly selects unsampled images from the production bucket
- Creates task JSONs in the "labelstudio/tasks/randomsampling" folder

#### Testing the Feedback Loop

1. Go to http://{public-node-ip}:5000
2. Upload test images from the /data/food11 folder 
3. Let's perform random sampling and label studio sync on demand by executing below commands in SSH 

```bash
docker exec scheduler python /app/scripts/random_sampling.py
# argument 1 for syncing project 1
docker exec scheduler python3 app/scripts/sync_script.py 1
```

 and go to http://{public-node-ip}:8080 and login to see the tasks created by random sampling. 

4. Complete the random sampling tasks and provide your prediction for the image.



### Set aside samples for which model has low confidence

Our second method identifies images where the model has low confidence in its prediction, making them valuable for retraining.

Use the below command to modify app.py :

```bash
nano /home/cc/eval-loop-chi/gourmetgram/app.py
```

1. Import Task Creation Function for low confidence tasks

Add this import to app.py:

```python
from gourmetgram_utils.feedback_tasks import create_low_confidence_task
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

#### Testing the Feedback Loop

1. Go to http://{public-node-ip}:5000.
2. Upload test images from the /data/lowconfidence folder in data.
3. Let's sync Label Studio on demand by executing 
```bash 
docker exec scheduler python3 /app/scripts/sync_script.py 2
```
and then go to http://{public-node-ip}:8080 and login to see the tasks created by low confidence predictions.
4. Complete the low confidence tasks by giving your prediction for the image.




### Get explicit feedback from users

Our third method enables users to provide feedback when they think the model's prediction is incorrect. This feedback may be sparse (some users won't bother giving feedback even if the label is wrong) and noisy (some users may give incorrect feedback). We can get human annotators to label this data, too.

Use the below command to modify app.py :

```bash
nano /home/cc/eval-loop-chi/gourmetgram/app.py
```

1. Import Task Creation Function for user feedback tasks and add the flag icon SVG

```python
from gourmetgram_utils.feedback_tasks import create_user_feedback_task

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


#### Testing the Feedback Loop

1. Go to http://{public-node-ip}:5000.
2. Upload test images from the data/userfeedback/ folder.
3. Provide negative feedback for the prediction
3. Let's sync Label Studio on demand by executing this in SSH
```bash
docker exec scheduler python3 /app/scripts/sync_script.py 3
```
and go to http://{public-node-ip}:8080 and login to see the tasks created by user feedback tasks. Complete the user feedback tasks.

Now that we've collected labeled data from human annotators in Label Studio, we need to process these annotations and organize them for model retraining. The labeled data is currently stored in the /labelstudio/output/ path in our MinIO storage system.

!!Make sure you've finished the annotation tasks in the Label Studio. 

To synchronize the annotation results with our MinIO Object Store on demand:

```bash
docker exec scheduler python3 /app/scripts/sync_script.py 
```

This script executes our synchronization utility, which:

- Retrieves completed annotation results from Label Studio
- Converts them to standardized JSON format
- Distributes them to their respective project directories in the /output folder of labelstudio bucket

Navigate to the MinIO web interface at http://{public-node-ip}:9001 and inspect the /output/ directory within the labelstudio bucket.
We will find output JSON files within each project folder.

Now we need to use this annotation data for model retraining. This below script does the following:

- Extracts the human-verified labels from the annotation results
- Retrieves the corresponding images from our production storage
- Organizes these images into class-specific buckets based on their corrected labels
- Creates a structured dataset ready for model retraining

```bash
docker exec scheduler python3 /app/scripts/process_outputs.py
```

Navigate to the MinIO web interface at http://{public-node-ip}:9001 and inspect the cleanproduction, lowconfidence and userfeedback buckets to find the structured dataset.


### Get explicit labels from users

Our last method is to allow users to explicitly label their images, by changing the label that is assigned by the classifier. This feedback may be sparse (some users won't bother giving feedback even if the label is wrong) and noisy (some users may give incorrect feedback).

Use the below command to modify app.py :

```bash
nano /home/cc/eval-loop-chi/gourmetgram/app.py
```
2. Add to imports at the top of the file : 

```python
from gourmetgram_utils.feedback_tasks import create_output_json

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

4. Update feedback function : 

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

1. Go to application interface at http://{public-node-ip}:5000
2. Upload test images from the data/userfeedback/ directory
3. Locate the pencil icon adjacent to the prediction and use it to select the correct classification from the dropdown menu
4. Process the corrections by executing:

```bash
docker exec scheduler python3 /app/scripts/process_outputs.py
```
5. Navigate to the MinIO web interface at http://{public-node-ip}:9001 and inspect the userfeedback2 buckets to find the structured dataset based on the user class predictions.


## Delete resources

When we are finished, we must delete the VM server instance to make the resources available to other users.

We will execute the cells in this notebook inside the Chameleon Jupyter environment.

Run the following cell, and make sure the correct project is selected. 


```python
from chi import server, context
import chi, os, time, datetime

context.version = "1.0" 
context.choose_project()
context.choose_site(default="KVM@TACC")
```


```python
username = os.getenv('USER') # all exp resources will have this prefix
s = server.get_server(f"node-eval-loop-{username}")
s.delete()
```



<hr>

<small>Questions about this material? Contact Fraida Fund</small>

<hr>

<small>This material is based upon work supported by the National Science Foundation under Grant No. 2230079.</small>

<small>Any opinions, findings, and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect the views of the National Science Foundation.</small>
