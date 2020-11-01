import os
import json
from google.cloud import pubsub_v1

def topic_push(event, context):
    """Triggered by a change to a Cloud Storage bucket.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    file = event
    GCS_BUCKET = file['bucket']
    FILENAME = file['name']
    GCP_PROJECT = os.environ['GCP_PROJECT']
    TOPIC = os.environ['push_topic']
    data = {
        'filepath': "gs://" + GCS_BUCKET + "/" + FILENAME,
        'filename': FILENAME,
        'bucket': GCS_BUCKET
    }

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GCP_PROJECT, TOPIC)

    publisher.publish(topic_path, json.dumps(data).encode('utf-8'))
    print("Published data: " + json.dumps(data))