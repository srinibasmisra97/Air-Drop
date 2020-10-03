# Air Drop API Server

The API Server for the Air Drop system is written in Python3.8 and Flask.

There are three parts in this server:
1. Startup Script.
2. Configs.
3. APIs.

## Setup

Required:
1. Python 3.
2. Virtualenv

Create a virtual environment:
```shell script
virtualenv -p python3 venv
```

Activate the virtual environment:
```shell script
source /path/to/virtual/environment/bin/activate
```

Install required python packages:
```shell script
pip install -r requirements.txt
```

## APIs

This is the meat of the server. 

There are three APIs:
1. GET /api/health
2. GET /api/pull
3. GET /api/download

Before we can execute the APIs, the `subscriber` and the `Storage Client` need to be instantiated.

```python
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(SERVICE_ACCOUNTS_DIRECTORY, "service-account-file.json")

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(GCP_PROJECT, SUBSCRIPTION_ID)

storage_client = storage.Client(GCP_PROJECT)
bucket = storage_client.bucket(GCS_BUCKET)
```

### GET /api/health

This API is used only for health checks. It directly returns a `200 OK` JSON response.

The response received is:
```json
{
    'success': true,
    'msg': 'health is ok'
}
``` 

### GET /api/pull

This API checks if there are any new messages in the Pub/Sub topic.

It first pulls the messages from the topic.
```
response = subscriber.pull(request={"subscription": subscription_path, "max_messages": NUM_MESSAGES})
```

After getting the response object, it goes through all of them, and downloads the files from the GCS Bucket and stores it in the local file system of the server.

```python
filenames = []
ack_ids = []
for received_message in response.received_messages:
    ack_ids.append(received_message.ack_id)
    data = json.loads(received_message.message.data.decode('utf8').replace("'", '"'))
    blob = bucket.blob(data['filename'])
    blob.download_to_file(file_obj=open(os.path.join(DOWNLOAD_FOLDER, str(data['filename'])), 'wb'))
    print("Downloaded file {} to {}".format(data['filename'], os.path.join(DOWNLOAD_FOLDER, data['filename'])))
    filenames.append(data['filename'])
```

After the files are downloaded, the Pub/Sub messages need to be acknowledged, so that they don't repeat.

```python
if len(filenames) > 0:
    subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": ack_ids})
```

### GET /api/download

This API is used to download the file.

It accespts a query parameter called `file` which contains the filename. 

If the file is present in the server, then it is automatically downloaded. Otherwise a `404 NOT FOUND` error is thrown.

Here we use the `send_from_directory` function from Flask, which allows us to send a file as a response.

**But there is a catch!**

Generally, if you try to open a file which is browser readable, the browser will open it instead of it downloading to your machine.

To handle this scenario, and to forcefully download it, we are going to add the `Content-Disposition` header.

By default the `Content-Disposition` header is set to `inline`. 

If the `Content-Disposition` header is `inline` then the browser will open it.

However, if we set the `Content-Disposition` header to `attachment`, then the browser will be forced to download it.

One more additional configuration we need to do is, set the `Content-Disposition` header as `attachment; filename="filename"`.

This would download the file and save it as the filename specified, otherwise it'll be downloaded with the URI path as the filename.

```python
response = make_response(send_from_directory(directory=DOWNLOAD_FOLDER, filename=filename))
response.headers['Content-Disposition'] = 'attachment; filename="' + filename + '"'
return response
```

## Configs

The configuration of the API server is set using a config file called the `environment.cfg` in the `configs` folder.

The config file follows the general cfg file syntax.

A config environment needs to be created and the parameters are passed under that.

An example would be:
```
[DEV]
GCP_PROJECT = gcp-project-name
SUBSCRIPTION_ID = gcp-subscription-id
GCS_BUCKET = gcs-bucket-name
DOWNLOAD_FOLDER = download-folder
SUBSCRIPTION_TIMEOUT = 5.0
NUM_MESSAGES = 3
SERVICE_ACCOUNTS_DIRECTORY = service-accounts-folder
```

The config file is imported using the `configparser` package.

```python
CONFIG_ENV = os.environ.get("CONFIG_ENV") if os.environ.get("CONFIG_ENV") else "DEV"
CONFIG_FILEPATH = os.path.join(os.getcwd(), "configs", "environment.cfg")

cfg = configparser.RawConfigParser()
cfg.read(CONFIG_FILEPATH)

GCP_PROJECT = str(cfg.get(CONFIG_ENV, "GCP_PROJECT"))
SUBSCRIPTION_ID = str(cfg.get(CONFIG_ENV, "SUBSCRIPTION_ID"))
GCS_BUCKET = str(cfg.get(CONFIG_ENV, "GCS_BUCKET"))
DOWNLOAD_FOLDER = str(cfg.get(CONFIG_ENV, "DOWNLOAD_FOLDER"))
SUBSCRIPTION_TIMEOUT = float(cfg.get(CONFIG_ENV, "SUBSCRIPTION_TIMEOUT"))
NUM_MESSAGES = int(cfg.get(CONFIG_ENV, "NUM_MESSAGES"))
SERVICE_ACCOUNTS_DIRECTORY = str(cfg.get(CONFIG_ENV, "SERVICE_ACCOUNTS_DIRECTORY"))
```

## Startup Script

To start the server we technically need a single command:
```
python server.py
```

However, we need to have an environment variable defined before starting the server.

The `CONFIG_ENV` environment variable needs to be set. This value will be used to choose which config section is selected from the `environment.cfg`.

The entire startup script would be:
```shell script
#!/bin/bash
export CONFIG_ENV="PROD"
/path/to/python /path/to/server.py
```