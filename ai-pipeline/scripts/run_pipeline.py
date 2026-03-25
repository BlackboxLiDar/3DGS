#!/usr/bin/env python3
import sys
from pathlib import Path


def _add_src_to_path():
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    sys.path.insert(0, str(src_path))


def _setup_gpu():
    """Disable cuDNN if it fails to initialize (e.g. Blackwell GPUs)."""
    try:
        import torch
        if torch.cuda.is_available():
            try:
                # Test cuDNN with a small tensor
                x = torch.randn(1, 1, 3, 3, device="cuda")
                torch.nn.functional.conv2d(x, torch.randn(1, 1, 1, 1, device="cuda"))
            except RuntimeError:
                torch.backends.cudnn.enabled = False
                print("cuDNN disabled (unsupported GPU arch), using native CUDA kernels")
    except ImportError:
        pass


def main():
    _add_src_to_path()
    _setup_gpu()
    from pipeline.run_pipeline import main as run_main

    run_main()


if __name__ == "__main__":
    main()
