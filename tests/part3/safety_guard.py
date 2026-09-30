"""
Safety Guard for GradeFlow tests/part3 Sandbox.
Enforces strict file write boundaries:
- Writing into cacmaubaithi -> RuntimeError
- Writing anywhere outside tests/part3/ -> RuntimeError
DO NOT MODIFY PRODUCTION FILES.
"""

import os
import sys
from pathlib import Path

SANDBOX_ROOT = Path(r"c:\Users\Thang\Downloads\chamdiembaithiweb\tests\part3").resolve()
CACMAU_ROOT = Path(r"c:\Users\Thang\Downloads\chamdiembaithiweb\cacmaubaithi").resolve()
REPO_ROOT = Path(r"c:\Users\Thang\Downloads\chamdiembaithiweb").resolve()
CACMAU_ROOT = (REPO_ROOT / "cacmaubaithi").resolve()
ANH_ROOT = (REPO_ROOT / "anh").resolve()
SANDBOX_ROOT = (REPO_ROOT / "tests" / "part3").resolve()

FORBIDDEN_DIRS = [CACMAU_ROOT, ANH_ROOT]


def validate_write_path(path):
    """
    Checks if path is allowed for writing.
    Must be strictly inside tests/part3/ or OS Temp folder.
    """
    if not path:
        return

    path_obj = Path(path).resolve()
    temp_dir = Path(os.environ.get("TEMP", "C:\\Users\\Thang\\AppData\\Local\\Temp")).resolve()

    # Always block any write into dataset directories
    for forbidden in FORBIDDEN_DIRS:
        try:
            path_obj.relative_to(forbidden)
            raise RuntimeError(f"SAFETY GUARD VIOLATION: Write inside dataset folder is strictly forbidden! Target: {path_obj}")
        except ValueError:
            pass

    # Allow writes inside tests/part3/ or OS Temp folder
    try:
        path_obj.relative_to(SANDBOX_ROOT)
        return
    except ValueError:
        pass

    try:
        path_obj.relative_to(temp_dir)
        return
    except ValueError:
        pass

    raise RuntimeError(f"SAFETY GUARD VIOLATION: Write outside tests/part3 is forbidden! Target: {path_obj}")


def install_safety_guard():
    """
    Patches file writing functions in Python runtime and OpenCV to enforce safety boundaries.
    """
    # Patch cv2.imwrite if cv2 is imported
    try:
        import cv2
        _orig_imwrite = cv2.imwrite

        def safe_imwrite(filename, img, params=None):
            validate_write_path(filename)
            if params is not None:
                return _orig_imwrite(filename, img, params)
            return _orig_imwrite(filename, img)

        cv2.imwrite = safe_imwrite
    except Exception:
        pass

    # Patch built-in open for write modes ('w', 'wb', 'a', 'ab', '+')
    _orig_open = open

    def safe_open(file, mode='r', *args, **kwargs):
        if any(m in mode for m in ('w', 'a', '+', 'x')):
            validate_write_path(file)
        return _orig_open(file, mode, *args, **kwargs)

    import builtins
    builtins.open = safe_open


# Auto-install when safety_guard is imported
install_safety_guard()
