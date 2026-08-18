# Lessons Learned

The 18 lessons distilled from the deployment, organized by phase.

## Telnet & Router Setup

1. **Disable auto-updates in NVRAM before doing anything else.** A firmware upgrade wipes telnet. There is no recovery without re-running the bkerler exploit.
2. **Netgear V7 firmware replaces password-based telnet login with SSH keys.** Anything below V6.3.6.2 is confirmed-working by bkerler; V6.3.8.5 was tested manually and works; V7+ is unsupported.
3. **`passwd` over telnet kills telnet.** Setting a new root password via the standard Unix `passwd` command triggers Netgear's ODM watchdog, which re-runs `telnetd-enable.sh` and may break your session.

## Guest Network

4. **The guest DHCP daemon is `dni_guest_udhcpd`, not dnsmasq.** UCI `dhcp_option` settings on `dhcp.@dnsmasq[0]` are silently ignored for the guest pool. The workaround is to overwrite `/tmp/dni_udhcpd_guest.conf` and restart the daemon on every boot.
5. **WPS Push Button Configuration does NOT work on guest VAPs.** Only the main VAPs (`ath0`/`ath1`/`ath2`) support WPS. You must pair cameras via the original Arlo base station first, then power it off.
6. **Same SSID + same WPA-PSK = no factory reset needed.** Cameras only care about the SSID and the PSK. If you clone both from the real base station to the Orbi guest network, they roam automatically.

## Firewall

7. **Netgear's ODM chains (`ODM_FORWARD`) run BEFORE user rules.** The guest zone has `forward=REJECT` by default, so `-A FORWARD` does nothing. Use `-I FORWARD 1` to insert your rules at the top.
8. **Do NOT add SNAT on the camera → server path.** SNATing the source to `172.14.1.1` causes a hairpin NAT loop on the Orbi (the server's SYN-ACK gets delivered to the router itself). Standard camera models do NOT require traffic to appear from the gateway IP. Only Video Doorbells (AAD1001) may need it.
9. **Make your `S99arlo` script idempotent.** Old `iptables` rules accumulate across reboots if you only `-A`. Use `while iptables -D ...; do :; done` to clean before adding.

## Camera Pairing

10. **Cameras may send a `status` message BEFORE a full `registerSet`.** VMC4040P in particular wakes from deep sleep and skips straight to status. The original arlo-cam-api crashes with `AttributeError` on `device.ip = self.ip` because `DeviceDB.from_db_serial` returns None. Fix: auto-register as a Camera with `SystemModelNumber='VMC4040P'` default. (PR #31)
11. **`VMC4040P` RTSP port is 554, NOT 555.** Some online docs say 555 for the Ultra/4K models; the VMC4040P uses 554. Always try 554 first, fall back to 555.
12. **`BatPercent` is the canonical battery field name.** Not `BatteryLevel`, not `BatteryPercent`, not `Batt`. The full set of useful fields is `BatPercent`, `Bat1Volt`, `ChargingState`, `SignalStrengthIndicator`, `WifiRSSI`, `Temperature`, `Uptime`, `PIREvents`, `PIRTriggers`, `MotionStreamed`, `UserStreamed`, `Streamed`, `FailedStreams`, `CameraOnline`, `CameraOffline`, `IRLEDsOn`, `SpotlightEnabled`, `WifiConnectionCount`, `SystemFirmwareVersion`, `HardwareRevision`, `WifiChannel`, `PoweredOn`, `CriticalBatStatus`, `ChargerTech`, `BatTech`.

## arlo-cam-api Server

13. **`threading.Thread(target=app.run(host='0.0.0.0'))` evaluates `app.run(...)` EAGERLY before constructing the Thread.** This starts Flask on the main thread, blocks it in werkzeug's select loop, and makes any subsequent `.start()` unreachable. Fix: `threading.Thread(target=app.run, kwargs={'host': '0.0.0.0'})`. (PR #29)
14. **Cameras tolerate only `MaxMissedBeaconTime` missed basestation beacons (default 30) before dropping off WiFi.** arlo-cam-api sends no periodic traffic after the initial handshake, so cameras eventually hibernate for hours. Fix: a `BeaconThread` that sends a `statusRequest` every 60s. (PR #30)
15. **`POST /device/<serial>/userstreamactive` was a no-op** — all code commented out, always returned `{"result": true}` without actually calling `device.set_user_stream_active`. Fix: read `active` from the body, validate, and call the method. (PR #31)

## Snapshot & Streaming

16. **Continuous RTSP streaming kills battery cameras in days.** Arlo battery cameras are designed for event-based recording: sleep 99%, wake for 5–10 s per event. Use `MediaMTX` with `sourceOnDemand: yes` and `sourceOnDemandCloseAfter: 1s` so the camera's RTSP is only up when someone is actually watching.
17. **PyAV tries RTSP port 555 first, fall back to 554.** VMC4040P uses 554; some Ultra/4K models use 555. The `arlo-snapshot` service in this repo handles both.
18. **`SnapshotOnMotion: true`** (arlo-cam-api config) hooks into the PIR alert handler and POSTs to the `arlo-snapshot` sidecar. Battery-friendly: no polling, frames are only captured when motion happens. (PR #31)

## WiFi & Mesh (Orbi)

19. **After a `wifi reload` / `wifi` restart, the Orbi's 5GHz-low radio (`wifi2`) can come up with an EMPTY SSID on its VAPs** (`ath2` = main 5GHz, `ath21` = guest 5GHz). The UCI config stays correct, but the live interface gets `ESSID:""` / `Access Point: Not-Associated`. This is a driver/firmware bring-up race. When it happens, the **LAN `hyd` mesh daemon fails to start** (`wlanifBSteerControlCmnStoreSSID: invalid ESSID length 0, ifName: ath2`), so the Orbi GUI shows the **satellites as "disconnected"** even though their backhaul radios are physically associated — and roaming/performance degrade. **Diagnose:** `iwconfig ath2; iwconfig ath21` (empty ESSID?) and `ps w | grep hyd` (LAN instance `-P 7777` missing?). **Fix:** `wifi down wifi2; wifi up wifi2` (or full `wifi`), then `/etc/init.d/hyd restart`; verify both `hyd` instances (`-P 7777` LAN + `-P 8888` guest). No persistent config changes — it only re-applies what UCI already had. See `rbr760/orbi-satellite-check.exp` for a read-only diagnostic.