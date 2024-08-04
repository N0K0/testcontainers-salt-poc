FROM ubuntu:22.04

ARG SALT_VERSION
# Crash if the version is not set
RUN test -n "${SALT_VERSION}"

LABEL org.opencontainers.image.authors="n0k0@hacky.software"
LABEL org.opencontainers.image.version="${SALT_VERSION}"

USER root

RUN apt-get update && \
	apt-get install -y wget curl binutils patchelf

RUN curl -fsSL -o /etc/apt/keyrings/salt-archive-keyring-2023.gpg https://repo.saltproject.io/salt/py3/ubuntu/24.04/amd64/SALT-PROJECT-GPG-PUBKEY-2023.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/salt-archive-keyring-2023.gpg arch=amd64] https://repo.saltproject.io/salt/py3/ubuntu/24.04/amd64/${SALT_VERSION} noble main" | tee /etc/apt/sources.list.d/salt.list

RUN apt-get update && \
    apt-get install -y salt-minion && \
    salt-pip install pygit2==1.14.1

# Add CMD that makes the container busy wait forever \
CMD [ "tail", "-f", "/dev/null" ]