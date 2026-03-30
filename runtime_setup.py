import os
import tempfile
from pathlib import Path


def configure_runtime_environment():
    base_cache_dir = Path(tempfile.gettempdir()) / "interactive-text-analysis"
    matplotlib_dir = base_cache_dir / "matplotlib"
    huggingface_dir = base_cache_dir / "huggingface"

    matplotlib_dir.mkdir(parents=True, exist_ok=True)
    huggingface_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_dir))
    os.environ.setdefault("HF_HOME", str(huggingface_dir))
