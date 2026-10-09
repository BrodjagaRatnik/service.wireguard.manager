""" ./resources/lib/io_atomic.py """
import os
import tempfile
from logger import log_message


def atomic_write_text(target_path, content):
    dir_path = os.path.dirname(target_path)
    fd, tmp_path = tempfile.mkstemp(prefix=".wgm_tmp_", dir=dir_path)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)
        return True
    except Exception as write_err:
        log_message(f"IO Atomic: Failed writing {target_path}: {write_err}", 3)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False
