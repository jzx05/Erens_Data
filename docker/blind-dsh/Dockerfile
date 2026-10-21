FROM node:24-bookworm-slim

# The dsh package is mounted read-only at /opt/dsh by blind_docker.sh.
# This avoids npm installs and native compilation inside the image.
USER node
WORKDIR /workspace
ENV HOME=/workspace \
    DSH_HOME=/workspace/.dsh-home

ENTRYPOINT ["node", "/opt/dsh/lib/bin.js"]
