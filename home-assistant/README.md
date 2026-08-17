# Home Assistant Integration

Drop the YAML files in this directory into your Home Assistant `packages/`, `templates/`, and `automations/` folders, then add to your `configuration.yaml`:

```yaml
homeassistant:
  packages:
    arlo_cameras: !include packages/arlo_cameras.yaml.example
    arlo_wake: !include packages/arlo_wake.yaml
```

## What you get

- 4 REST sensors (battery, WiFi RSSI, temperature, charging state, PIR events, motion/user/total streams, etc.) — one per camera
- ~60 derived `template:` sensors and `binary_sensor:`s (per-camera breakdown of the above)
- 4 `input_boolean.camera_*_armed` + 4 `input_boolean.camera_*_led` (HA-side state synced to the camera)
- 4 `rest_command.camera_*_arm` + 4 `rest_command.camera_*_led` (POSTs to the arlo-cam-api)
- 4 `rest_command.arlo_wake_*` + 4 `rest_command.arlo_snapshot_*`
- 1 `input_select.arlo_wake_mode` (off / periodic / on-demand)
- 1 `input_number.arlo_wake_interval_minutes`
- 1 `script.arlo_wake_all` (parallel wake + delay + parallel snapshot)
- 9 wake-related automations
- 4 button-card templates (one per camera, wake + snapshot on press)

## Prerequisites

- Home Assistant ≥ 2024.x
- The `arlo-cameras.yaml.example` file must be edited to replace `XXXXXXXXXXXX` with your actual camera serials (`http://192.168.1.48:5000/device` returns the list).
- The arlo-cam-api server must be reachable at the IP you configure (`http://192.168.1.48:5000` by default).
- The arlo-snapshot sidecar must be reachable at `http://192.168.1.48:8000`.