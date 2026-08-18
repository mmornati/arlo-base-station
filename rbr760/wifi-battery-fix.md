# RBR760 — WiFi-Layer Battery Fix for Cameras

This document is the companion reference for the [blog post 4](https://github.com/mmornati/mornati-blog) of the Arlo series. It captures the two WiFi-layer changes that, together with Post 1's networking setup and Posts 2/3's application stack, keep Arlo cameras connected on a Netgear Orbi RBR760 without the ~30-minute re-registration cycle that drains their batteries.

## Why the fix is needed

The real Arlo base station never disassociates a sleeping camera. It keeps them in 802.11 power-save with DTIM/PS-Poll, and includes a vendor-specific IE in beacons listing the associated cameras. The relevant patents are cited in the blog post.

The Netgear Orbi RBR760 guest WiFi, by contrast, ships with a default inactivity timeout (`inact`) of 300 seconds. After five minutes of radio silence from a sleeping camera, the AP disassociates it. The camera then wakes up, gets a new DHCP lease, and re-registers from scratch — roughly every 30 minutes. The application layer is fine; the WiFi layer is the bottleneck.

## The two changes

### 1. Raise the inactivity timeout to the firmware maximum

```
uci set wireless.Guest2.inact='65535'
uci set wireless.Guest5.inact='65535'
uci commit wireless

cfg80211tool ath02 inact 65535
cfg80211tool ath21 inact 65535
```

The `inact` value is a 16-bit field, so 65535 seconds (~18.2 hours) is the maximum. The setting persists across reboots via `/lib/wifi/qcawificfg80211.sh` (line ~4069), which passes it through to `cfg80211tool` on every wireless restart. No script patch is required.

### 2. Raise the guest DHCP lease to 24 hours

In `rbr760/S99arlo`, change `option lease 1800` to `option lease 86400`. Restart the script:

```
/etc/rc.d/S99arlo restart
```

The guest DHCP daemon is the proprietary `dni_guest_udhcpd` (not `dnsmasq`). The main LAN DHCP daemon is a separate process and is untouched.

## Verification

After applying both fixes, the live state should match:

| Check | Command | Expected |
|---|---|---|
| `ath02` inact | `cfg80211tool ath02 get_inact` | `inact = 65535` |
| `ath21` inact | `cfg80211tool ath21 get_inact` | `inact = 65535` |
| UCI `Guest2` | `uci get wireless.Guest2.inact` | `65535` |
| UCI `Guest5` | `uci get wireless.Guest5.inact` | `65535` |
| Guest DHCP lease | `grep lease /tmp/dni_udhcpd_guest.conf` | `option lease 86400` |
| Guest DHCP pid | `ps w | grep dni_guest_udhcpd | grep -v grep` | one process |

The `S99arlo.log` should show no `re-registration` events for the cameras after they have first connected and registered.

## What can go wrong — the wifi2 mesh race

A `wifi reload` (or any UCI-driven wireless restart) can trigger a bring-up race on `wifi2` (5 GHz-low). The VAPs on `ath2` (main 5 GHz-low) and `ath21` (guest 5 GHz-low) may come up with empty SSIDs, which causes the LAN `hyd` mesh daemon to fail with:

```
HYDR wlanif ERR: wlanifBSteerControlCmnStoreSSID: invalid ESSID length 0, ifName: ath2
Failed to initialize wlanif/wlb/modules
```

When that happens, the satellites show as "disconnected" in the Orbi GUI even though the backhaul link is fine. Recovery:

```
wifi down wifi2
wifi up wifi2
/etc/init.d/hyd restart
```

Verify afterwards:

```
ps w | grep 'hyd '           # expect TWO instances: 7777 LAN + 8888 guest
iwconfig ath2 | grep ESSID   # expect a real SSID
iwconfig ath21 | grep ESSID  # expect a real SSID
```

The `inact` setting survives the recovery because UCI is the source of truth and `qcawificfg80211.sh` re-applies it.

## Rollback

```
uci delete wireless.Guest2.inact
uci delete wireless.Guest5.inact
uci commit wireless
cfg80211tool ath02 inact 300
cfg80211tool ath21 inact 300

sed -i 's/option lease 86400/option lease 1800/' /etc/rc.d/S99arlo
sed -i 's/option lease 86400/option lease 1800/' /tmp/dni_udhcpd_guest.conf
/etc/rc.d/S99arlo restart
```

## Warnings

- **Never run `passwd` on a Netgear Orbi router.** It rewrites `/etc/passwd` in a way that breaks telnet access. Change the admin password through the web GUI.
- **Never set `skip_inactivity_poll=1`.** It makes idle stations *more* likely to be disconnected, not less. The right knob is `inact`.
- **The `inact` value is 16-bit.** It is impossible to set a literal "never". The maximum is `65535` (~18.2 hours). In practice, a camera that wakes for any reason will re-associate long before the timer fires.

## Known limitations

- Satellite guest VAPs (`RBS760`) are not directly verifiable — there is no telnet service on the satellite IPs. The UCI setting lives on the main router; the satellites receive it via Orbi's config sync over the guest backhaul VLAN 4094.
- `inact` is not a substitute for `BeaconIntervalSeconds` in `arlo-cam-api`. The two settings are independent — `inact` controls the AP-side disassociation timer; `BeaconIntervalSeconds` controls the application-layer keepalive. Both are needed for a battery-friendly fleet.

## Disable auto-updates

A firmware update wipes the telnet service and all customisations. Disable the auto-updater:

```
nvram set orbi_auto_upgrade=0
nvram set auto_check_for_upgrade=0
nvram set auto_update=0
nvram commit
```

This is the single highest-leverage change to protect the setup.
