FROM python:3.12-slim-bookworm

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY

# Install Node 24 from the official portable tarball. Python's stdlib handles
# HTTPS and xz extraction, so no apt/curl/xz packages are needed.
COPY install_node.py /tmp/install_node.py
RUN python3 /tmp/install_node.py && rm -f /tmp/install_node.py

USER 1000:1000
WORKDIR /workspace
ENV HOME=/workspace \
    DSH_HOME=/workspace/.dsh-home

ENTRYPOINT ["node", "/opt/dsh/lib/bin.js"]
