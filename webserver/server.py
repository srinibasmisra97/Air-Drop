import json
import os
import configparser
from flask import Flask, jsonify, request, send_from_directory, make_response
from google.cloud import pubsub_v1, storage

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

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(SERVICE_ACCOUNTS_DIRECTORY, "air-drop.json")

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(GCP_PROJECT, SUBSCRIPTION_ID)

storage_client = storage.Client(GCP_PROJECT)
bucket = storage_client.bucket(GCS_BUCKET)

app = Flask(__name__)


@app.route('/api/health', methods=['GET'])
def health_status():
    return jsonify({
        'success': True,
        'msg': 'health is ok'
    })


@app.route('/api/pull', methods=['GET'])
def pull_messages():
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.mkdir(DOWNLOAD_FOLDER)

    response = subscriber.pull(request={"subscription": subscription_path, "max_messages": NUM_MESSAGES})

    filenames = []
    ack_ids = []
    for received_message in response.received_messages:
        ack_ids.append(received_message.ack_id)
        data = json.loads(received_message.message.data.decode('utf8').replace("'", '"'))
        blob = bucket.blob(data['filename'])
        blob.download_to_file(file_obj=open(os.path.join(DOWNLOAD_FOLDER, str(data['filename'])), 'wb'))
        print("Downloaded file {} to {}".format(data['filename'], os.path.join(DOWNLOAD_FOLDER, data['filename'])))
        filenames.append(data['filename'])

    if len(filenames) > 0:
        subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": ack_ids})

    filtered_filenames = []

    for name in filenames:
        if name not in filtered_filenames:
            filtered_filenames.append(name)

    return jsonify({
        'success': True,
        'data': filtered_filenames,
        'count': len(filtered_filenames)
    })


@app.route('/api/download', methods=['GET'])
def download_file():
    if 'file' not in request.args:
        return jsonify({
            'success': False,
            'msg': 'file not provided'
        }), 400

    filename = request.args.get('file')

    print("Download from {}".format(os.path.join(DOWNLOAD_FOLDER, filename)))

    if not os.path.exists(os.path.join(DOWNLOAD_FOLDER, filename)):
        return jsonify({
            'success': False,
            'msg': 'file not found'
        }), 404

    response = make_response(send_from_directory(directory=DOWNLOAD_FOLDER, filename=filename))
    response.headers['Content-Disposition'] = 'attachment; filename="' + filename + '"'
    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)