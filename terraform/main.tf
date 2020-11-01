# Defining the provider for google.
provider "google" {
    project = "dev-trials-project"
    credentials = file("/Users/srinibasmisra/Documents/terraform.json")
    region  = "us-central1"
    zone    = "us-central1-a"
}

# Creating the required service accounts
resource "google_service_account" "air_drop_service_account" {
    account_id  = "tf-air-drop-sa"
    display_name    = "tf-air-drop-sa"
}

resource "google_service_account" "gcsfuse_service_account" {
    account_id  = "tf-air-drop-gcsfuse"
    display_name    = "tf-air-drop-gcsfuse"
}

resource "google_project_iam_member" "pubsub_subscriber" {
    project = "dev-trials-project"
    role    = "roles/pubsub.subscriber"
    member  = "serviceAccount:tf-air-drop-sa@dev-trials-project.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "storage_object_viewer" {
    project = "dev-trials-project"
    role    = "roles/storage.objectViewer"
    member  = "serviceAccount:tf-air-drop-sa@dev-trials-project.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "storage_admin" {
    project = "dev-trials-project"
    role    = "roles/storage.admin"
    member  = "serviceAccount:tf-air-drop-gcsfuse@dev-trials-project.iam.gserviceaccount.com"
}

# Creating the compute engine VM.
# Reserving static ip.
resource "google_compute_address" "air_drop_address" {
    name    = "air-drop-ipv4-address"
}

# Defining the custom image to be used.
data "google_compute_image" "air_drop_gce_image" {
    project = "dev-trials-project"
    name = "air-drop"
}

# Creating VM.
resource "google_compute_instance" "air_drop_vm" {
    name    = "air-drop-tf-vm"
    machine_type    = "f1-micro"
    zone    = "us-central1-a"

    tags    = ["http-server", "https-server"]

    boot_disk {
        initialize_params {
            image = data.google_compute_image.air_drop_gce_image.self_link
        }
    }

    network_interface {
        network = "default"
        access_config {
            nat_ip = google_compute_address.air_drop_address.address
        }
    }
}

# Creating GCS Buckets.
resource "google_storage_bucket" "music-artefacts" {
    name = "music-artefacts"
    location = "us-central1"

    uniform_bucket_level_access = true
}

resource "google_storage_bucket" "gcf-sources" {
    name = "gcf-sources"
    location = "us-central1"
}

# Creating Pub/Sub Topic and Subscriptions.
resource "google_pubsub_topic" "tf-air-drop-topic" {
    name = "tf-air-drop-topic"
}

resource "google_pubsub_subscription" "tf-air-drop-subscription" {
    name = "tf-air-drop-subscription"
    topic = google_pubsub_topic.tf-air-drop-topic.name

    retain_acked_messages = false
}

# Creating cloud function.
resource "google_storage_bucket_object" "air-drop-cf-archive" {
    name = "air-drop-cf.zip"
    bucket = google_storage_bucket.gcf-sources.name
    source = "/Users/srinibasmisra/Documents/Projects/Audio-File-Automation/cloud-function/air-drop.zip"
}

resource "google_cloudfunctions_function" "air-drop-cf" {
    name = "tf_air_drop_publisher"
    description = "Cloud function to push new storage objects to topic."
    runtime = "python37"

    source_archive_bucket = google_storage_bucket.gcf-sources.name
    source_archive_object = google_storage_bucket_object.air-drop-cf-archive.name
    entry_point = "topic_push"

    event_trigger {
        event_type = "google.storage.object.finalize"
        resource = google_storage_bucket.music-artefacts.name
    }

    environment_variables = {
        push_topic = "tf-air-drop-topic"
    }
}