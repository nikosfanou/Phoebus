import random
import string
import traceback
import os
import time
import json
import json5

from datetime import datetime
import uuid

def read_json(file):
    with open(file, 'r') as fp:
        return json5.load(fp=fp)

def write_json(file, data):
    with open(file, "w+") as fp:
        fp.write(json.dumps(data, indent=4))

def extract_log_msg(exception):
    main_msg = str(exception)
    tb = traceback.extract_tb(exception.__traceback__)
    last_call = tb[-1]
    log_msg = f"{main_msg} at {last_call.filename}, line {last_call.lineno}, in {last_call.name}"
    return log_msg

def find_file(start_dir, filename):
    for root, _, files in os.walk(start_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None

def format_time(seconds):
    """Converts seconds into weeks, days, hours, minutes, and seconds."""
    weeks = seconds // (7 * 24 * 3600)
    seconds %= (7 * 24 * 3600)
    days = seconds // (24 * 3600)
    seconds %= (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    parts = []
    if weeks:
        parts.append(f"{weeks} weeks")
    if days:
        parts.append(f"{days} days")
    if hours:
        parts.append(f"{hours} hours")
    if minutes:
        parts.append(f"{minutes} minutes")
    if seconds or not parts:
        parts.append(f"{seconds} seconds")
    return ', '.join(parts)

def list_files(folder, file_extension):
    return [
        f for f in os.listdir(folder)
        if f.endswith(file_extension) and os.path.isfile(os.path.join(folder, f))
    ]

def get_datetime_iso_format():
    timestamp = time.time()
    datetime_obj = datetime.fromtimestamp(timestamp)
    # return datetime_obj.strftime("%Y%m%d%H%M%S")
    return datetime_obj.astimezone().isoformat()

def generate_uuid():
    return str(uuid.uuid4()).replace('-', '')

def random_char(y):
    return ''.join(random.choice(string.ascii_letters) for x in range(y))