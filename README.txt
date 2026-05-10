# AccidentDetect — Setup & Run Guide

## Folder Structure

accident_system/
├── app.py               ← Flask server
├── detection.py         ← Real OpenCV detection + email
├── requirements.txt
├── templates/
│   └── index.html       ← Dashboard UI
├── static/
│   └── style.css
├── uploads/             ← Auto-created on first run
└── outputs/             ← Processed clips saved here


## Step 1 — Install Python dependencies

Open a terminal in the accident_system folder and run:

    pip install -r requirements.txt


## Step 2 — Configure your Gmail App Password

Open detection.py and update these 3 lines at the top:

    SENDER_EMAIL   = "your_gmail@gmail.com"
    RECEIVER_EMAIL = "alert_target@gmail.com"
    APP_PASSWORD   = "your_16_char_app_password"

To get a Gmail App Password:
  1. Go to myaccount.google.com → Security
  2. Enable 2-Step Verification
  3. Search "App Passwords" → Create one for "Mail"
  4. Paste the 16-character password above


## Step 3 — Run the server

    python app.py

Then open your browser and go to:

    http://localhost:10000


## How it works

1. You upload a video through the dashboard
2. OpenCV scans every frame for sudden motion spikes (collision detection)
3. If a spike is found for 4+ consecutive frames → accident flagged
4. A 6-second clip is extracted (3s before + 3s after the accident frame)
5. "ACCIDENT DETECTED" overlay + timestamp is burned into the clip
6. Gmail alert is sent to your receiver email
7. The clip appears in the dashboard with a Download button


## Tuning Detection Sensitivity

In detection.py, adjust these two values:

    MOTION_THRESHOLD     = 3000   # Lower = more sensitive (catches smaller movements)
    CONSECUTIVE_REQUIRED = 4      # Lower = triggers faster

For dashcam/CCTV footage: try MOTION_THRESHOLD = 5000
For slow/steady cameras:  try MOTION_THRESHOLD = 1500
