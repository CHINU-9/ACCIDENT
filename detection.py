import cv2
import os
import numpy as np
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

OUTPUT_FOLDER = "outputs"

# -----------------------------------
# CONFIGURATION — edit these
# -----------------------------------

SENDER_EMAIL    = "chinmayabehera248@gmail.com"
RECEIVER_EMAIL  = "techglacier60@gmail.com"
APP_PASSWORD    = "kbzltltyqllgevtl"   # Gmail App Password

# Cluster-based detection settings
WINDOW_SECONDS   = 2.0   # sliding window size to find peak motion cluster
TOP_PERCENTILE   = 92    # only frames above this percentile are "high motion"
MIN_CLUSTER_FRAMES = 6   # minimum frames in cluster to count as an event


# -----------------------------------
# EMAIL ALERT
# -----------------------------------

def send_email_alert(clip_filename, accident_time):
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "🚨 Accident Detected — Clip Ready"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = RECEIVER_EMAIL

        body = (
            f"An accident was detected in the uploaded video.\n\n"
            f"Detected at : {accident_time}\n"
            f"Saved clip  : {clip_filename}\n\n"
            f"Log in to your dashboard to review the footage."
        )
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False


# -----------------------------------
# CLUSTER-BASED ACCIDENT DETECTION
# -----------------------------------

def detect_accident_frame(video_path, progress_callback=None):
    """
    Instead of triggering on the FIRST spike (which catches normal traffic),
    this scans ALL frames, builds a motion score timeline, then finds the
    single biggest sustained cluster — that's the accident.

    Strategy:
    1. Record motion score for every frame
    2. Find the threshold above which frames are "high motion" (top percentile)
    3. Find the densest cluster of high-motion frames using a sliding window
    4. Return the center frame of that cluster
    """
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS) or 24

    if total == 0:
        cap.release()
        return None, total

    # --- Pass 1: collect all frame scores ---
    scores = []
    prev_gray = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if prev_gray is not None:
            diff  = cv2.absdiff(prev_gray, gray)
            score = int(np.sum(diff))
            scores.append(score)
        else:
            scores.append(0)

        prev_gray = gray
        frame_idx += 1

        if progress_callback and total > 0:
            pct = int((frame_idx / total) * 55)
            progress_callback(pct, f"Scanning frame {frame_idx}/{total}...")

    cap.release()

    if not scores:
        return None, total

    # --- Pass 2: find threshold (top percentile of scores) ---
    threshold = float(np.percentile(scores, TOP_PERCENTILE))

    # --- Pass 3: sliding window — find window with most high-motion frames ---
    window_frames = max(1, int(WINDOW_SECONDS * fps))
    best_count  = 0
    best_center = None

    for start in range(len(scores) - window_frames + 1):
        window = scores[start : start + window_frames]
        count  = sum(1 for s in window if s >= threshold)
        if count > best_count:
            best_count  = count
            best_center = start + window_frames // 2

    if best_count < MIN_CLUSTER_FRAMES:
        print(f"⚠ Best cluster only {best_count} frames — below minimum, no accident flagged")
        return None, total

    print(f"✅ Accident cluster: center frame {best_center} ({best_center/fps:.2f}s), density {best_count}/{window_frames} frames")
    return best_center, total


# -----------------------------------
# MAIN PROCESS FUNCTION
# -----------------------------------

def process_video(video_path, progress_callback=None):
    def cb(pct, stage):
        if progress_callback:
            progress_callback(pct, stage)
        print(f"[{pct}%] {stage}")

    cb(2, "Opening video...")

    cap = cv2.VideoCapture(video_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    cb(5, "Analyzing motion vectors...")

    # --- Detect accident frame ---
    accident_frame, total = detect_accident_frame(video_path, progress_callback=lambda p, s: cb(p, s))

    accident_detected = accident_frame is not None

    if not accident_detected:
        # Fallback: use middle of video
        accident_frame = total_frames // 2
        print("⚠ No motion spike detected — using midpoint as fallback")

    cb(62, "Accident frame located — extracting clip...")

    # --- Extract 6-second clip around accident ---
    start_frame = max(0, accident_frame - 3 * fps)
    end_frame   = min(total_frames, accident_frame + 3 * fps)

    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    timestamp = datetime.now().strftime("%d-%m-%y_%H-%M-%S")
    filename  = timestamp + ".avi"
    output_path = os.path.join(OUTPUT_FOLDER, filename)

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    current = start_frame
    clip_length = end_frame - start_frame

    cb(65, "Writing overlay onto clip...")

    while current < end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        # --- Red flashing border on accident frames ---
        is_accident_zone = abs(current - accident_frame) < fps  # 1 sec around accident
        if is_accident_zone:
            cv2.rectangle(frame, (0, 0), (width - 1, height - 1), (0, 0, 220), 8)

        # --- "ACCIDENT DETECTED" overlay ---
        label = "ACCIDENT DETECTED" if accident_detected else "NO ACCIDENT"
        color = (0, 0, 255) if accident_detected else (0, 200, 80)
        cv2.putText(frame, label, (40, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3, cv2.LINE_AA)

        # --- Timestamp overlay ---
        current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        cv2.putText(frame, current_time, (40, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        # --- Frame counter ---
        cv2.putText(frame, f"Frame: {current}", (width - 160, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)

        out.write(frame)
        current += 1

        # Report clip-write progress (60–95%)
        if progress_callback and clip_length > 0:
            done = current - start_frame
            pct = 65 + int((done / clip_length) * 30)
            progress_callback(pct, f"Writing frame {done}/{clip_length}...")

    cap.release()
    out.release()

    cb(96, "Clip saved — sending email alert...")

    accident_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    if accident_detected:
        send_email_alert(filename, accident_time)

    cb(100, "Done")

    print(f"✅ Saved: {output_path} | Accident: {accident_detected}")

    return {
        "output_path": output_path,
        "accident_detected": accident_detected,
        "accident_frame": accident_frame,
        "filename": filename,
    }
