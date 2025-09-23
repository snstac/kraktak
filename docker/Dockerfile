# Download base image ubuntu 22.04
FROM ubuntu:22.04

# LABEL about the custom image
LABEL description="ADS-B to TAK Gateway."

# Disable Prompt During Packages Installation
ARG DEBIAN_FRONTEND=noninteractive

# Update Ubuntu Software repository
RUN apt update
RUN apt upgrade -y
RUN apt install -y python3
RUN apt install -y python3-pip
RUN apt install -y python3-numpy
RUN apt install -y python3-zmq
RUN apt install -y python3-cryptography
RUN apt install -y rtl-sdr

# Install Python modules
RUN python3 -m pip install asyncinotify
RUN python3 -m pip install pymodes
RUN python3 -m pip install pyrtlsdr

# Build kraktak
COPY . /kraktak/
RUN cd /kraktak/ && python3 setup.py install easy_install 'kraktak[with_pymodes]'
RUN rm -R /kraktak/

# Copy kraktak configuration
RUN mkdir /etc/kraktak/
COPY kraktak-docker-example.conf /etc/kraktak/kraktak.conf

# Copy start.sh script and define default command for the container
COPY start.sh /start.sh
CMD ["./start.sh"]
