
To report bugs, please set the DEBUG=1 environment variable to collect logs:

```sh
DEBUG=1 kraktak
```

Or:

```sh linenums="1"
export DEBUG=1
kraktak
```

Or:

```sh linenums="1"
echo 'DEBUG=1' >> kraktak.ini
kraktak -c kraktak.ini
```

You can view systemd/systemctl/service logs via:

```journalctl -fu kraktak```

Please use GitHub issues for support requests. Please note that KrakTAK is free open source software and comes with no warranty. See LICENSE.