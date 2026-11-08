# BYD Battery-Box HV for Home Assistant

Monitor a legacy BYD Battery-Box HV from Home Assistant using the battery’s local web interface. The integration provides 17 standard sensors and can optionally expose the voltage of each cell as a separate sensor.

## Features

- **Shared polling** — One Home Assistant data coordinator refreshes the standard readings every 60 seconds. All sensors share the results. Network requests run in the background with connection and read timeouts.
- **Optional per-cell voltages** — Enable `cell_voltages` to discover the module and cell numbers reported by the battery. The integration creates one voltage sensor per discovered cell, so the number of sensors follows the installed configuration.
- **Power in watts** — The integration reads the unit reported by the battery and converts kilowatts to watts when needed. If the reported power has no recognized unit, it uses pack voltage multiplied by current when both readings are available.
- **Display precision** — Voltage, current, and energy sensors default to three decimal places. Home Assistant’s per-entity display settings take precedence.

Tested on a legacy BYD Battery-Box HV 10.2 running firmware **V3.013C**. With eight B-Plus H 1.28 modules, the integration exposed **128 individual cell voltages**.

## Installation

1. Copy `__init__.py`, `manifest.json`, and `sensor.py` into the `custom_components/byd_hv_box/` directory under your Home Assistant configuration directory.
2. Add the following entry to your existing `sensor:` configuration. Replace the placeholders with your battery’s local address and web interface credentials.
3. Restart Home Assistant to load the integration.

```yaml
sensor:
  - platform: byd_hv_box
    host: YOUR_BYD_BOX_IP
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    cell_voltages: true
```

`cell_voltages` defaults to `false`. Set it to `true` to enable per-cell monitoring. Existing installations can keep their current `host`, `username`, and `password` values.

## Sensors

| Group | Readings |
| --- | --- |
| Electrical | Array voltage, pack voltage, current, power, and state of charge |
| Temperature | System temperature and minimum and maximum cell temperatures |
| Cell extremes | Minimum and maximum cell voltages, plus the reported positions of the voltage and temperature extremes |
| Lifetime totals | Total charge energy, total discharge energy, and total cycle count |
| Optional cell monitoring | Individual cell voltages, identified by array, module, and cell number |

An example cell entity ID is `sensor.byd_hv_array_01_module_07_cell_01_voltage`. Home Assistant keeps the registered entity IDs for existing sensors when their unique IDs stay the same.

## How cell monitoring works

The **Run Data** page exposes the cell voltages for one selected module at a time. When cell monitoring is enabled, the integration steps through the modules in the currently selected array, checks that each response matches the requested module, and attempts to restore the original selection after the refresh. This adds network requests and can briefly change the module displayed in the battery’s web interface.

## Troubleshooting

- **No BYD readings** — Check that Home Assistant can reach the battery’s web interface. Check the Home Assistant logs for timeouts or HTTP errors. An HTTP 401 means the battery rejected the request’s authentication.
- **Only one module’s cells appear** — Check the logs for module selection errors. The integration can read the currently displayed module directly. Reading the other modules requires the firmware to accept the module selection request.
- **Cell values look rounded** — Check the entity’s display precision in Home Assistant. An explicit setting there overrides the integration’s default.
- **Changes do not appear after replacing `sensor.py`** — Restart Home Assistant to load the updated Python code.

## Credits

This integration is based on [Kilian Knoll’s original script](https://www.photovoltaikforum.com/thread/129771-byd-batteriespeicher-daten-programmatisch-auslesen/).

## License and disclaimer

This project is licensed under the GNU General Public License, version 3 or, at your option, any later version. See [LICENSE](LICENSE) for the full terms. The software is provided without warranty. Use it at your own risk.
