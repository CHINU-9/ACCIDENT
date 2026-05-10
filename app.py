from flask import Flask, render_template, request, redirect, send_from_directory, jsonify, Response
import os
import threading
import json
from detection import process_video

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Shared progress state per job
progress_store = {}


# -----------------------------------
# HOME PAGE
# -----------------------------------

@app.route("/")
def home():
    videos = []
    for f in os.listdir(OUTPUT_FOLDER):
        if f.endswith((".avi", ".mp4", ".mov")):
            videos.append(f)
    videos.sort(reverse=True)
    return render_template("index.html", videos=videos)


# -----------------------------------
# UPLOAD & PROCESS VIDEO
# -----------------------------------

@app.route("/upload", methods=["POST"])
def upload_video():
    file = request.files.get("video")
    if not file or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    upload_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(upload_path)

    job_id = file.filename

    # Run processing in background thread
    def run():
        progress_store[job_id] = {"stage": "Starting...", "pct": 0, "done": False, "error": None, "output": None, "accident": False}
        try:
            result = process_video(upload_path, progress_callback=lambda pct, stage: progress_store[job_id].update({"pct": pct, "stage": stage}))
            progress_store[job_id].update({
                "done": True,
                "output": os.path.basename(result["output_path"]),
                "accident": result["accident_detected"]
            })
        except Exception as e:
            progress_store[job_id].update({"done": True, "error": str(e)})

    threading.Thread(target=run, daemon=True).start()

    return jsonify({"job_id": job_id})


# -----------------------------------
# POLL PROGRESS
# -----------------------------------

@app.route("/progress/<job_id>")
def get_progress(job_id):
    state = progress_store.get(job_id, {"stage": "Waiting...", "pct": 0, "done": False, "error": None, "output": None, "accident": False})
    return jsonify(state)


# -----------------------------------
# LIST OUTPUT VIDEOS
# -----------------------------------

@app.route("/videos")
def list_videos():
    videos = []
    for f in sorted(os.listdir(OUTPUT_FOLDER), reverse=True):
        if f.endswith((".avi", ".mp4", ".mov")):
            videos.append(f)
    return jsonify(videos)


# -----------------------------------
# SERVE OUTPUT VIDEO
# -----------------------------------

@app.route("/outputs/<filename>")
def output_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


# -----------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
