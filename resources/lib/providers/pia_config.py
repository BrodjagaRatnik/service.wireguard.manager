"""
./resources/lib/providers/pia_config.py
Manages persistent API rate-limiting and connection cooldown states.
Saves expiration timestamps to file to prevent endpoint hammering.
Allows API client to make a maximum of 3 attempts within a rolling or fixed time frame of 600 seconds (10 minutes).
If a client exceeds 3 requests during this period, the system will block or throttle them 900 seconds (15 minutes).
"""
import os
import time
from logger import log_message

MAX_LATENCY = 0.05


class PiaHandshakeEngine:
    def __init__(self):
        self.cooldown_dir = "/storage/.kodi/userdata/addon_data/service.wireguard.manager"
        self.cooldown_file = os.path.join(self.cooldown_dir, ".pia_cooldown")
        self.history_file = os.path.join(self.cooldown_dir, ".pia_sync_history")

        self.max_attempts = 3
        self.time_window_seconds = 600.0
        self.cooldown_duration_seconds = 900.0

    def check_rate_limit(self):
        if os.path.exists(self.cooldown_file):
            try:
                with open(self.cooldown_file, "r") as f:
                    expiry = float(f.read().strip())
                remaining = int(expiry - time.time())
                if remaining > 0:
                    log_message(f"PIA Rate Limit: Active block detected. Remaining: {remaining}s", 2)
                    return True, remaining
                log_message("PIA Rate Limit: Cooldown record expired. Purging tracking file from disk.", 0)
                os.remove(self.cooldown_file)
            except Exception as read_err:
                log_message(f"PIA Rate Limit: Failed to parse cooldown manifest metadata: {read_err}", 3)
                return False, 0
        return False, 0

    def enforce_cooldown(self, seconds):
        log_message(f"PIA Rate Limit: Triggering state lock mechanism for {seconds} seconds.", 2)
        try:
            if not os.path.exists(self.cooldown_dir):
                os.makedirs(self.cooldown_dir)
            with open(self.cooldown_file, "w") as f:
                f.write(str(time.time() + float(seconds)))
            log_message("PIA Rate Limit: Cooldown state successfully written to storage.", 0)
        except Exception as write_err:
            log_message(f"PIA Rate Limit: Failed to save active block target to file: {write_err}", 3)

    def track_and_check_abuse(self):
        current_time = time.time()
        window_start = current_time - self.time_window_seconds
        valid_timestamps = []

        log_message("PIA Rate Limit: Checking historical API access patterns.", 0)

        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    lines = f.readlines()
                for line in lines:
                    ts = float(line.strip())
                    if ts > window_start:
                        valid_timestamps.append(ts)
            except Exception as history_err:
                log_message(f"PIA Rate Limit: Could not read previous synchronization records: {history_err}", 3)

        log_message(f"PIA Rate Limit: Valid attempts in current window: {len(valid_timestamps)} / {self.max_attempts}", 0)

        if len(valid_timestamps) >= self.max_attempts:
            log_message("PIA Rate Limit: Abuse threshold exceeded. Initializing automatic lockout protocols.", 3)
            self.enforce_cooldown(self.cooldown_duration_seconds)
            try:
                if os.path.exists(self.history_file):
                    os.remove(self.history_file)
            except Exception as purge_err:
                log_message(f"PIA Rate Limit: Failed to wipe synchronization history from disk: {purge_err}", 3)
            return True

        valid_timestamps.append(current_time)
        try:
            if not os.path.exists(self.cooldown_dir):
                os.makedirs(self.cooldown_dir)
            with open(self.history_file, "w") as f:
                for ts in valid_timestamps:
                    f.write(f"{ts}\n")
            log_message("PIA Rate Limit: Successfully appended current execution tracking timestamp.", 0)
        except Exception as append_err:
            log_message(f"PIA Rate Limit: Failed to document active usage markers: {append_err}", 3)

        return False
