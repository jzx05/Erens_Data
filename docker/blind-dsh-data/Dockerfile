FROM ale-blind-dsh-py

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY

USER root
RUN pip install --no-cache-dir \
      pandas \
      pyarrow \
      numpy \
      scipy \
      openpyxl
USER 1000:1000

WORKDIR /workspace
ENV HOME=/workspace \
    DSH_HOME=/workspace/.dsh-home

ENTRYPOINT ["node", "/opt/dsh/lib/bin.js"]
