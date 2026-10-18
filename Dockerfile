FROM cyberbotics/webots.cloud:R2025a-ubuntu22.04

ARG PROJECT_PATH
RUN mkdir -p $PROJECT_PATH
COPY . $PROJECT_PATH

RUN python3 -m pip install --no-cache-dir numpy requests opencv-python-headless