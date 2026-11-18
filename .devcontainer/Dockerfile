FROM mcr.microsoft.com/devcontainers/python:3.3.3-3.12-bookworm@sha256:10717c456fb0ac3a9a78c7d9d405599b589d8faf59865f7596a4b26995b7b14c

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        dbus-x11 gnome-keyring gir1.2-secret-1 libgirepository1.0-dev libcairo2-dev pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir uv==0.12.5

USER vscode
ENV PATH="/home/vscode/.local/bin:${PATH}"
# PyGObject 3.50 supports Bookworm's GI libraries and keeps the MSAL cache encrypted.
RUN uv tool install --python python3.12 --with 'PyGObject==3.50.0' 'ms-fabric-cli==1.7.0'
