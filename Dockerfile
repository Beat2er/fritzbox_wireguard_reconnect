# basic image that includes main.py and executes it in endless loop, consider flusing the output
FROM python:3.8-slim
LABEL maintainer="Beat2er"
LABEL version="1.0"
LABEL name="fritzbox_reconnect_vpn"

RUN apt-get update && apt-get install -y wget gnupg2

# Install Google Chrome
# Adding trusting keys to apt for repositories
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
# Adding Google Chrome to the repositories
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
# Updating apt to see and install Google Chrome
RUN apt-get -y update
# Magic happens
RUN apt-get install -y google-chrome-stable

#clean up
RUN apt-get clean

# allow to pass env variables via compose: ENV_IP, ENV_USER, ENV_PASS, ENV_VPN_NAMES (sep by ;), ENV_LOOP_DELAY, ENV_HEADLESS
ARG ENV_IP=192.168.178.1
ARG ENV_USER=admin
ARG ENV_PASS=admin
ARG ENV_VPN_NAMES=vpn1;vpn2
ARG ENV_LOOP_DELAY=60
ENV ENV_HEADLESS=True

COPY main.py /main.py
# requiremets.txt
COPY requirements.txt /requirements.txt
RUN pip install -r requirements.txt

CMD ["python", "-u", "/main.py"]

