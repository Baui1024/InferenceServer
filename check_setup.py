#!/usr/bin/env python3
"""Pre-flight check for InferenceServer prerequisites.

Run before 'uv sync' to verify GPU drivers and CUDA are available.
Usage:  python check_setup.py          # check only
        python check_setup.py --fix    # attempt to install missing components (Linux)
"""

import subprocess
import sys
import shutil
import platform

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def ok(msg: str):
    print(f"  {GREEN}✓{RESET} {msg}")

def warn(msg: str):
    print(f"  {YELLOW}!{RESET} {msg}")

def fail(msg: str):
    print(f"  {RED}✗{RESET} {msg}")

def heading(msg: str):
    print(f"\n{BOLD}{msg}{RESET}")


def run(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return -1, "command not found"
    except subprocess.TimeoutExpired:
        return -2, "timed out"


def check_nvidia_driver() -> tuple[bool, str]:
    code, out = run(["nvidia-smi", "--query-gpu=driver_version,name,memory.total",
                     "--format=csv,noheader,nounits"])
    if code != 0:
        return False, ""
    return True, out


def check_cuda_toolkit() -> tuple[bool, str]:
    code, out = run(["nvcc", "--version"])
    if code != 0:
        return False, ""
    for line in out.splitlines():
        if "release" in line.lower():
            return True, line.strip()
    return True, out.splitlines()[-1] if out else ""


def check_python_cuda() -> tuple[bool, str]:
    """Check if PyTorch can see CUDA (only if torch is installed)."""
    try:
        import torch
        if torch.cuda.is_available():
            return True, f"torch {torch.__version__}, CUDA {torch.version.cuda}, GPU: {torch.cuda.get_device_name(0)}"
        return False, f"torch {torch.__version__} installed but CUDA not available"
    except ImportError:
        return False, "torch not installed (run 'uv sync' first)"


def check_tensorrt() -> tuple[bool, str]:
    try:
        import tensorrt
        return True, f"TensorRT {tensorrt.__version__}"
    except ImportError:
        return False, "not installed"


def is_linux() -> bool:
    return platform.system() == "Linux"


def is_root() -> bool:
    try:
        import os
        return os.getuid() == 0
    except AttributeError:
        return False  # Windows


def fix_nvidia_driver():
    if not is_linux():
        fail("Auto-install only supported on Ubuntu/Debian Linux")
        return False

    if not is_root():
        fail("Run with sudo to install drivers: sudo python check_setup.py --fix")
        return False

    if not shutil.which("ubuntu-drivers"):
        warn("ubuntu-drivers not found, installing...")
        code, out = run(["apt-get", "install", "-y", "ubuntu-drivers-common"], timeout=60)
        if code != 0:
            fail(f"Failed to install ubuntu-drivers-common: {out}")
            return False

    print("    Detecting recommended driver...")
    code, out = run(["ubuntu-drivers", "list"], timeout=30)
    if code != 0:
        fail(f"ubuntu-drivers list failed: {out}")
        return False
    print(f"    Available: {out}")

    print("    Installing recommended driver (this may take a few minutes)...")
    code, out = run(["ubuntu-drivers", "install"], timeout=600)
    if code != 0:
        fail(f"Driver install failed: {out}")
        return False

    ok("NVIDIA driver installed. A REBOOT is required!")
    return True


def fix_cuda_toolkit():
    if not is_linux():
        fail("Auto-install only supported on Ubuntu/Debian Linux")
        return False

    if not is_root():
        fail("Run with sudo: sudo python check_setup.py --fix")
        return False

    # Install CUDA toolkit (runtime, not full dev) via NVIDIA's repo
    print("    Installing CUDA toolkit via apt...")
    # First check if nvidia-cuda-toolkit is available
    code, out = run(["apt-get", "install", "-y", "nvidia-cuda-toolkit"], timeout=300)
    if code != 0:
        fail(f"CUDA toolkit install failed: {out}")
        warn("Install manually: https://developer.nvidia.com/cuda-downloads")
        return False

    ok("CUDA toolkit installed")
    return True


def main():
    fix_mode = "--fix" in sys.argv
    all_ok = True

    print(f"\n{BOLD}InferenceServer — Setup Check{RESET}")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print(f"  Python:   {sys.version.split()[0]}")

    # 1. NVIDIA Driver
    heading("1. NVIDIA GPU Driver")
    found, info = check_nvidia_driver()
    if found:
        ok(f"Driver installed — {info}")
    else:
        fail("nvidia-smi not found — no NVIDIA driver installed")
        all_ok = False
        if fix_mode:
            fix_nvidia_driver()
        elif is_linux():
            warn("Run with --fix to auto-install, or:")
            warn("  sudo apt install nvidia-driver-560  (or latest)")
            warn("  Then reboot")
        else:
            warn("Download from: https://www.nvidia.com/Download/index.aspx")

    # 2. CUDA Toolkit
    heading("2. CUDA Toolkit")
    found, info = check_cuda_toolkit()
    if found:
        ok(info)
    else:
        warn("nvcc not found — CUDA toolkit not installed (or not in PATH)")
        warn("Note: PyTorch bundles its own CUDA runtime, so this may work anyway")
        if fix_mode and is_linux():
            fix_cuda_toolkit()
        elif is_linux():
            warn("Run with --fix to auto-install, or:")
            warn("  sudo apt install nvidia-cuda-toolkit")

    # 3. PyTorch + CUDA
    heading("3. PyTorch CUDA")
    found, info = check_python_cuda()
    if found:
        ok(info)
    else:
        warn(info)
        if "not installed" in info:
            warn("Run 'uv sync' to install Python dependencies first")
        else:
            all_ok = False
            warn("PyTorch can't access CUDA — check driver/CUDA installation")

    # 4. TensorRT
    heading("4. TensorRT")
    found, info = check_tensorrt()
    if found:
        ok(info)
    else:
        warn("TensorRT not installed — engine compilation won't be available")
        warn("Run 'uv sync' to install from pyproject.toml")

    # Summary
    heading("Summary")
    if all_ok:
        ok("All critical prerequisites met — ready to run!")
    else:
        fail("Some prerequisites are missing — see above for details")
        if not fix_mode and is_linux():
            warn("Run 'sudo python check_setup.py --fix' to attempt auto-install")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
