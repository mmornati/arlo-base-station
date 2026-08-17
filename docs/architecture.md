# Architecture

```
Internet
    |
RBR760 Router (telnet-rooted, 192.168.1.1)
    |
    +-- LAN (192.168.1.x)
    |       |
    |       +-- Home Assistant (192.168.1.32)
    |       +-- arlo server (192.168.1.48) running:
    |               arlo-cam-api  :4000  camera registration
    |                              :5000  REST API
    |               arlo-snapshot :8000  still image proxy (on demand)
    |               MediaMTX      :8554  on-demand RTSP relay (cam1..camN)
    |
    +-- Guest WiFi (SSID: ARLO_VMB_XXXXXXXXXX)
    |       |
    |       +-- RBS760 Satellite 1 (extends guest WiFi via mesh)
    |       +-- RBS760 Satellite 2 (extends guest WiFi via mesh)
    |       |
    |       +-- Camera 1 @ 192.168.2.X   RTSP: rtsp://192.168.2.X:554/live
    |       +-- Camera 2 @ 192.168.2.X   RTSP: rtsp://192.168.2.X:554/live
    |       +-- Camera N @ 192.168.2.X   RTSP: rtsp://192.168.2.X:554/live
    |
    All cameras: gateway = 172.14.1.1 (virtual, on RBR760, on br-guest)
    Port 4000/4100 traffic DNAT'd to 192.168.1.48:4000/4100
    Guest net (192.168.2.0/24) is isolated from LAN; MediaMTX bridges RTSP
```

## Traffic flow (camera → server)

1. Camera boots, joins SSID `ARLO_VMB_XXXXXXXXXX` (the original Arlo base station's SSID, now re-broadcast by the Orbi guest network).
2. RBR760's `dni_guest_udhcpd` (proprietary DHCP daemon) hands the camera:
   - IP in `192.168.2.0/24`
   - Default gateway `172.14.1.1` (the magic value the Arlo firmware hard-codes as "the basestation")
   - DNS `1.1.1.1` / `1.0.0.1`
3. Camera opens a TCP connection to `172.14.1.1:4000` (port 4000 is the Arlo basestation protocol).
4. RBR760's `iptables` PREROUTING DNAT rule (inserted by `S99arlo` on every boot) rewrites the destination to `192.168.1.48:4000`.
5. `arlo-cam-api` on the server accepts the registration, sends back the `REGISTER_SET_INITIAL` payload (`PIRTargetState: Armed`, sensitivities, etc.).
6. The camera now considers itself paired with a basestation; motion events, status updates, and RTSP work as if the real Arlo base station were there.

## Traffic flow (Home Assistant → server)

- HA's REST sensors poll `http://192.168.1.48:5000/device/<serial>` every 5 minutes → returns battery, WiFi RSSI, temperature, PIR event counts, etc.
- HA's `rest_command`s issue POSTs to the same API for arm/disarm, PIR LED control, and the on-demand wake (`/device/<serial>/userstreamactive`).
- HA's `picture-entity` cards fetch stills from `http://192.168.1.48:8000/snapshot/<serial>` (the `arlo-snapshot` sidecar).
- HA's live-stream cards use `rtsp://192.168.1.48:8554/camN` (MediaMTX, on-demand).