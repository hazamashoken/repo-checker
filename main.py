import os
import json
import shutil
import logging
import requests
from flask import Flask, request, jsonify
from git import Repo
from paramiko import Ed25519Key
from paramiko import RSAKey
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".c", ".cpp", ".h", ".hpp", "Makefile"}
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", None)

SSH_KEY_PATH= os.environ.get("SSH_KEY_PATH", "~/.ssh/id_ed25519")
X_SECRET = os.environ.get("X_SECRET")

if X_SECRET is None:
    raise Exception("X_SECRET is required")

def load_ssh_key(private_key_path):
    try:
        if "rsa" in private_key_path:
            key = RSAKey(filename=private_key_path)
            return key
        elif "ed25519" in private_key_path:
            key = Ed25519Key(filename=private_key_path)
            return key
    except Exception as e:
        logging.error(f"Failed to load SSH key: {e}")
        return None

ssh_key_path = os.path.expanduser(SSH_KEY_PATH)
ssh_key = load_ssh_key(ssh_key_path)
if not ssh_key:
    raise Exception("Failed to load SSH key")

def clone_repo(repo_url, clone_dir, ssh_key):
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)
    try:
        Repo.clone_from(repo_url, clone_dir, env={"GIT_SSH_COMMAND": f"ssh -i {ssh_key}"})
        return True
    except Exception as e:
        logging.error(f"Failed to clone repo: {e}")
        return False

def not_in_dotgit(path):
    return ".git" not in path

def check_files(repo_dir):
    invalid_files = []
    for root, _, files in os.walk(repo_dir):
        for file in files:
            if not is_valid_extension(file) and not_in_dotgit(os.path.join(root, file)):
                invalid_files.append(os.path.join(root, file))
    return invalid_files


def is_valid_extension(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS or filename == "Makefile"


def send_discord_notification(invalid_files, users, project):
    message = '\n'.join(invalid_files)
    payload = {"embeds": [
    {
      "title": f"{users[0].get("login", "login")} - {project['slug']}",
      "description": message,
      "url": f"https://projects.intra.42.fr/projects/{project['slug']}/projects_users/{users[0].get("projects_user_id", "projects_user_id")}",
      "color": 5814783
    }
    ],}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
        if response.status_code == 204:
            logging.info("Discord notification sent successfully")
        else:
            logging.error(f"Failed to send Discord notification: {response.text}")
    except Exception as e:
        logging.error(f"Error sending Discord webhook: {e}")

def send_discord_success(users, project):
    payload = {
        "embeds": [
    {
      "title": f"{users[0].get("login", "login")} - {project['slug']}",
      "description": "All files match the allowed extensions.",
      "url": f"https://projects.intra.42.fr/projects/{project['slug']}/projects_users/{users[0].get("projects_user_id", "projects_user_id")}",
      "color": 5814783
    }
    ], }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
        if response.status_code == 204:
            logging.info("Discord notification sent successfully")
        else:
            logging.error(f"Failed to send Discord notification: {response.text}")
    except Exception as e:
        logging.error(f"Error sending Discord webhook: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    secret = request.headers.get("X-Secret")
    if secret != X_SECRET:
        return jsonify({"error": "Bad Request"}), 401
    data = request.get_json()
    repo_url = data.get("repo_url")
    if not repo_url:
        return jsonify({"error": "Repository URL is required"}), 400
    users = data.get("users")
    project = data.get("project")

    clone_dir = "./temp-repo"


    if not clone_repo(repo_url, clone_dir, ssh_key_path):
        return jsonify({"error": "Failed to clone repo"}), 500

    invalid_files = check_files(clone_dir)
    shutil.rmtree(clone_dir)

    if invalid_files:
        send_discord_notification(invalid_files, users, project)
        return jsonify({"message": "Repository processed successfully, but some files don't match the allowed extensions."}), 200

    send_discord_success(users, project)
    return jsonify({"message": "Repository processed successfully, all files match the allowed extensions."}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
