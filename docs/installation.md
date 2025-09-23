KrakTAK's functionality provided by a command-line program called `kraktak`.

There are several methods of installing KrakTAK. They are listed below, in order of complexity.

## Debian, Ubuntu, Raspberry Pi

Install KrakTAK, and prerequisite packages of [PyTAK](https://pytak.rtfd.io) & [AIRCOT](https://aircot.rtfd.io).

```sh linenums="1"
sudo apt update -qq
wget https://github.com/snstac/aircot/releases/latest/download/aircot_latest_all.deb
sudo apt install -f ./aircot_latest_all.deb
wget https://github.com/snstac/pytak/releases/latest/download/pytak_latest_all.deb
sudo apt install -f ./pytak_latest_all.deb
wget https://github.com/snstac/kraktak/releases/latest/download/kraktak_latest_all.deb
sudo apt install -f ./kraktak_latest_all.deb
```

> **N.B.** This installation method only supports `http://` & `file://` based ADS-B data feeds. To use TCP RAW (SBS-1) or TCP binary Beast protocols, you'll need to install pyModeS, see below.

## Windows, Linux

Install from the Python Package Index (PyPI) [Advanced Users]::

```sh
sudo python3 -m pip install kraktak
```

## TCP BaseStation (SBS-1) & TCP binary Beast support

If you'd like to read decoded ADS-B data over the network, you must install KrakTAK with the extra pymodes package:

```sh
sudo python3 -m pip install kraktak[with_pymodes]
```

## ADSBExchange.com Raspberry Pi

These instructions are exclusively for systems running the ADSBExchange.com Raspberry Pi image.

```sh linenums="1"
sudo apt update
sudo apt install -y python3-pip
sudo python3 -m pip install kraktak
```

## Docker

Build the docker container.

```sh linenums="1"
git clone https://github.com/snstac/kraktak.git
cd kraktak/
docker build -t kraktak .
```

Run the docker container with config folder mounted locally. Config files can be edited in the local folder ```/opt/docker/kraktak/```.

```sh linenums="1"
docker run -d -v /opt/docker/kraktak/:/etc/kraktak --name kraktak kraktak
```

## Developers

PRs welcome!

```sh linenums="1"
git clone https://github.com/snstac/kraktak.git
cd kraktak/
python3 setup.py install
```
