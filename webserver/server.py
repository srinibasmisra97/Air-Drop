import json
import os
from flask import Flask, jsonify, request, send_from_directory, make_response
from google.cloud import pubsub_v1, storage

GCP_PROJECT = 'dev-trials-project'
SUBSCRIPTION_ID = 'music-artefacts'
GCS_BUCKET = "srini-music-artifacts"
DOWNLOAD_FOLDER = "./downloads"
SUBSCRIPTION_TIMEOUT = 5.0
NUM_MESSAGES = 3

subscriber = pubsub_v1.SubscriberClient().from_service_account_file("./service-accounts/pull-messages-sa.json")
subscription_path = subscriber.subscription_path(GCP_PROJECT, SUBSCRIPTION_ID)

storage_client = storage.Client("GCP_PROJECT")
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

    messages = []
    ack_ids = []
    for received_message in response.received_messages:
        ack_ids.append(received_message.ack_id)
        data = json.loads(received_message.message.data.decode('utf8').replace("'", '"'))
        blob = bucket.blob(data['filename'])
        blob.download_to_filename(filename=os.path.join(DOWNLOAD_FOLDER, data['filename']))
        print("Downloaded file {} to {}".format(data['filename'], os.path.join(DOWNLOAD_FOLDER, data['filename'])))
        messages.append(data)

    if len(messages) > 0:
        subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": ack_ids})

    return jsonify({
        'success': True,
        'data': messages,
        'count': len(messages)
    })


@app.route('/api/download', methods=['GET'])
def download_file():
    if 'file' not in request.args:
        return jsonify({
            'success': False,
            'msg': 'file not provided'
        }), 400

    if not os.path.exists(DOWNLOAD_FOLDER):
        os.mkdir(DOWNLOAD_FOLDER)

    filename = request.args.get('file')

    response = make_response(send_from_directory(directory=DOWNLOAD_FOLDER, filename=filename))
    response.headers['Content-Disposition'] = 'attachment; filename="' + filename + '"'
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)