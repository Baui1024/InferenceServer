"""TensorRT engine compilation manager.

Handles on-demand compilation of YOLO .pt models to TensorRT .engine files,
scanning for available engines, and deletion.
"""

import asyncio
import os
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

# Directory to store compiled engine files
ENGINES_DIR = Path(__file__).resolve().parent.parent / "engines"

# Map of source .pt models available for compilation
COMPILABLE_MODELS = [
    "yolo11m.pt", "yolo11l.pt", "yolo11x.pt",
    "yolo26m.pt", "yolo26l.pt", "yolo26x.pt",
]


def _gpu_info() -> dict:
    """Detect NVIDIA GPU name and compute capability."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"name": None, "capability": None}
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        return {"name": name, "capability": f"{cap[0]}.{cap[1]}"}
    except Exception:
        return {"name": None, "capability": None}


def list_engines() -> list[dict]:
    """Return metadata for all compiled engine files."""
    ENGINES_DIR.mkdir(parents=True, exist_ok=True)
    engines = []
    for f in sorted(ENGINES_DIR.glob("*.engine")):
        stat = f.stat()
        engines.append({
            "filename": f.name,
            "source_model": f.stem + ".pt",
            "size_mb": round(stat.st_size / (1024 * 1024), 1),
        })
    return engines


def get_engine_path(filename: str) -> Optional[Path]:
    """Return the full path to an engine file, or None if it doesn't exist."""
    p = ENGINES_DIR / filename
    if p.exists() and p.suffix == ".engine":
        return p
    return None


def delete_engine(filename: str) -> bool:
    """Delete a compiled engine file. Returns True if deleted."""
    p = ENGINES_DIR / filename
    if p.exists() and p.suffix == ".engine":
        p.unlink()
        logger.info(f"Deleted engine: {filename}")
        return True
    return False


async def compile_engine(
    model_name: str,
    on_progress: Callable[[str, int], None],
) -> dict:
    """Compile a .pt model to a TensorRT .engine file.

    Args:
        model_name: Source model filename (e.g. "yolo26m.pt")
        on_progress: Callback(status_text, percent) for progress updates.

    Returns:
        dict with engine metadata on success.

    Raises:
        ValueError: If model_name is not in COMPILABLE_MODELS.
        RuntimeError: If compilation fails.
    """
    if model_name not in COMPILABLE_MODELS:
        raise ValueError(f"Unknown model: {model_name}")

    ENGINES_DIR.mkdir(parents=True, exist_ok=True)
    engine_filename = model_name.replace(".pt", ".engine")
    engine_path = ENGINES_DIR / engine_filename

    if engine_path.exists():
        on_progress("Engine already exists", 100)
        stat = engine_path.stat()
        return {
            "filename": engine_filename,
            "source_model": model_name,
            "size_mb": round(stat.st_size / (1024 * 1024), 1),
        }

    loop = asyncio.get_event_loop()

    def _do_export():
        from ultralytics import YOLO

        on_progress("Loading PyTorch model...", 5)
        model = YOLO(model_name)

        on_progress("Exporting to TensorRT (this takes several minutes)...", 10)
        export_path = model.export(
            format="engine",
            half=True,
            imgsz=640,
        )

        # ultralytics places the .engine next to the .pt source.
        # Move it to our engines directory.
        exported = Path(export_path)
        if exported.exists():
            target = ENGINES_DIR / engine_filename
            exported.rename(target)
            on_progress("Done!", 100)
            stat = target.stat()
            return {
                "filename": engine_filename,
                "source_model": model_name,
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
            }
        else:
            raise RuntimeError(f"Export completed but engine file not found at {exported}")

    on_progress("Starting compilation...", 0)
    result = await loop.run_in_executor(None, _do_export)
    return result
