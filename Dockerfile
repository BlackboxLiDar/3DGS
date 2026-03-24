FROM nvidia/cuda:12.8.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3.10-dev python3-pip \
    ffmpeg git wget \
    libgl1-mesa-glx libglib2.0-0 \
    cmake ninja-build \
    libboost-all-dev libeigen3-dev \
    libflann-dev libfreeimage-dev libmetis-dev \
    libgoogle-glog-dev libgtest-dev \
    libsqlite3-dev libglew-dev \
    qtbase5-dev libqt5opengl5-dev \
    libcgal-dev libceres-dev \
    && rm -rf /var/lib/apt/lists/*

# Build COLMAP with CUDA support
RUN git clone https://github.com/colmap/colmap.git /tmp/colmap && \
    cd /tmp/colmap && git checkout 3.11.1 && \
    mkdir build && cd build && \
    cmake .. -GNinja -DCMAKE_CUDA_ARCHITECTURES="86;89;100" && \
    ninja -j$(nproc) && ninja install && \
    rm -rf /tmp/colmap

# PyTorch with CUDA (install before requirements.txt to avoid CPU override)
WORKDIR /workspace
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu128

# Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir \
    --ignore-installed torch torchvision torchaudio \
    -r requirements.txt

# Copy project
COPY . .

ENTRYPOINT ["python3", "ai-pipeline/scripts/run_pipeline.py"]
