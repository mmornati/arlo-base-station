# Arlo Base Station Replacement

Self-hosted replacement for the Arlo base station, using:

- A **Netgear Orbi RBR760** (telnet-rooted) whose guest WiFi is hijacked to act as the camera basestation
- An **arlo-cam-api** Docker stack (with three upstream patches I contributed)
- An **arlo-snapshot** sidecar service for on-demand still images
- A **MediaMTX** RTSP relay for streaming
- A **Home Assistant** integration package

## Documentation

The full how-to lives in a 3-part blog series (announcement post coming soon).

1. **Networking & Gateway Hack** — telnet on the Orbi, `S99arlo` startup script, `dni_guest_udhcpd` workaround, ODM firewall quirks, the `172.14.1.1` virtual gateway trick, WPS pairing, troubleshooting.
2. **Services & Upstream Contributions** — Docker stack, MediaMTX, the `arlo-snapshot` sidecar, and the three PRs (#29, #30, #31) contributed to https://github.com/brianschrameck/arlo-cam-api.
3. **Home Assistant Integration** — REST sensors, template sensors, binary sensors, automations, button templates, Lovelace dashboard.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the diagram and traffic flow.

## Repository layout

```
rbr760/         Telnet-rooted Orbi RBR760 artifacts (S99arlo, expect helpers, NM dispatcher)
server/         Docker Compose + MediaMTX + arlo-cam-api patches
arlo-snapshot/  Custom Flask + PyAV on-demand snapshot service
home-assistant/ HA package (REST sensors, automations, templates)
docs/           Architecture diagram + lessons learned
```

## License

MIT — see [`LICENSE`](LICENSE).