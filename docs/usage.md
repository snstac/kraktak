## Command-line

Command-line usage is available by running ``kraktak -h``.

```
usage: kraktak [-h] [-c CONFIG_FILE] [-p PREF_PACKAGE]

options:
  -h, --help            show this help message and exit
  -c CONFIG_FILE, --CONFIG_FILE CONFIG_FILE
                        Optional configuration file. Default: config.ini
  -p PREF_PACKAGE, --PREF_PACKAGE PREF_PACKAGE
                        Optional connection preferences package zip file (aka data package).
```

## Run as a service / Run forever

1. Add the text contents below a file named `/etc/systemd/system/kraktak.service`  
  You can use `nano` or `vi` editors: `sudo nano /etc/systemd/system/kraktak.service`
2. Reload systemctl: `sudo systemctl daemon-reload`
3. Enable KrakTAK: `sudo systemctl enable kraktak`
4. Start KrakTAK: `sudo systemctl start kraktak`

### `kraktak.service` Content
```ini
[Unit]
Description=KrakTAK - Display Aircraft in TAK
Documentation=https://kraktak.rtfd.io
Wants=network.target
After=network.target
# Uncomment this line if you're running dump1090 & kraktak on the same computer:
# After=dump1090-fa.service

[Service]
RuntimeDirectoryMode=0755
ExecStart=/usr/local/bin/kraktak -c /etc/kraktak.ini
SyslogIdentifier=kraktak
Type=simple
Restart=always
RestartSec=30
RestartPreventExitStatus=64
Nice=-5

[Install]
WantedBy=default.target
```

> Pay special attention to the `ExecStart` line above. You'll need to provide the full local filesystem path to both your kraktak executable & kraktak configuration files.