FROM ubuntu@sha256:b1066385161d28ddf6bc7e7b28a9170eec11484c821d1a5150d176cbde41d7f7
ENV DEBIAN_FRONTEND=noninteractive
COPY portable-linux/apt-packages.lock /opt/apt-packages.lock
RUN apt-get update && awk '{print $1 "=" $2}' /opt/apt-packages.lock > /tmp/apt-specs && xargs -a /tmp/apt-specs apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/* /tmp/apt-specs
RUN python3 -m venv /opt/coop-gui && /opt/coop-gui/bin/pip install --upgrade pip==25.3
COPY requirements-launcher-linux.lock /opt/requirements-launcher.txt
COPY portable-linux/party-dependencies.lock /opt/party-dependencies.lock
RUN /opt/coop-gui/bin/pip install --require-hashes -r /opt/party-dependencies.lock && /opt/coop-gui/bin/pip install --no-deps -r /opt/requirements-launcher.txt && /opt/coop-gui/bin/pip check && /opt/coop-gui/bin/pip freeze > /opt/python-dependencies.lock && dpkg-query -W -f='${Package}\t${Version}\n' > /opt/apt-dependencies.lock
ENV QT_QPA_PLATFORM=offscreen
WORKDIR /work
