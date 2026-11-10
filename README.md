# BYD Battery-Box HV for Home Assistant

Monitor a legacy BYD Battery-Box HV through its local web interface. The integration provides 17 standard sensors and can optionally expose individual cell voltages and module diagnostics in Home Assistant.

## Features

- **Shared polling** — A single Home Assistant data coordinator refreshes the readings every 60 seconds. Sensors share the results. Network requests run in the background with connection and read timeouts.
- **Optional cell and module monitoring** — Enable `cell_voltages` to read individual cell voltages, module serial numbers, module voltages, cell voltage differences, temperature measurements, and the `BalanceCtrl` state shown for each cell. The integration discovers module, cell, and temperature sensor numbers from the data reported by the battery.
- **Power in watts** — The integration converts power reported in kilowatts to watts. If the power field has no recognized unit, it uses pack voltage multiplied by current when both readings are available.
- **Display precision** — Voltage, current, and energy sensors default to three decimal places. Home Assistant’s per-entity display settings take precedence.

Individual cell voltage monitoring was tested on a legacy BYD Battery-Box HV 10.2 running firmware **V3.013C**. The system reported **128 cell voltages** across eight B-Plus H 1.28 modules. The available diagnostics depend on the fields exposed by the battery’s web interface.

## Installation

1. Copy `__init__.py`, `manifest.json`, and `sensor.py` into `custom_components/byd_hv_box/` under your Home Assistant configuration directory.
2. Add the following platform entry to your `sensor:` configuration. If you already have a `sensor:` section, add the entry under that section. Replace the placeholders with your battery’s local address and web interface credentials.
3. Restart Home Assistant.

```yaml
sensor:
  - platform: byd_hv_box
    host: YOUR_BYD_BOX_IP
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    cell_voltages: true
```

`cell_voltages` defaults to `false`. Set it to `true` to enable both individual cell voltages and module diagnostics. Existing installations can keep their current `host`, `username`, and `password` values.

## Standard sensors

| Group | Readings |
| --- | --- |
| Electrical | Array voltage, pack voltage, current, power, and state of charge |
| Temperature | System temperature and minimum and maximum cell temperatures |
| Cell extremes | Minimum and maximum cell voltages, plus the reported positions of the voltage and temperature extremes |
| Lifetime totals | Total charge energy, total discharge energy, and total cycle count |

## Optional cell and module sensors

| Reading | Scope | Example entity ID |
| --- | --- | --- |
| Cell voltage | Per cell, in V | `sensor.byd_hv_array_01_module_07_cell_01_voltage` |
| Serial number | Per module | `sensor.byd_hv_array_01_module_07_serial_number` |
| Module voltage (`BattVol`) | Per module, in V | `sensor.byd_hv_array_01_module_07_voltage` |
| Cell voltage difference (`CellVolDiff`) | Per module, in V | `sensor.byd_hv_array_01_module_07_cell_voltage_delta` |
| Temperature (`CellTemp[…]`) | Per reported temperature measurement point, in °C | `sensor.byd_hv_array_01_module_07_temperature_sensor_01` |
| `BalanceCtrl` | Per reported cell, as `checked` or `unchecked` | `sensor.byd_hv_array_01_module_07_cell_01_balance_ctrl` |

`CellVolDiff` is the difference between the highest and lowest cell voltage reported for a module. For example, `0.002 V` equals `2 mV`. The `BalanceCtrl` sensor mirrors the checkbox shown on the **Run Data** page. The firmware’s interpretation of that checkbox is unverified.

The update preserves the unique IDs of existing standard and cell voltage sensors, so Home Assistant can reuse their registered entity IDs.

## How module polling works

The **Run Data** page shows readings for one selected module at a time. With `cell_voltages` enabled, the integration steps through the modules in the currently selected array, verifies the array and module in each response, and attempts to restore the original selection afterward. The selection displayed in the battery’s web interface may briefly change during a refresh.

Module diagnostics are read from the same responses as the individual cell voltages. They require no additional HTTP requests beyond those already used for cell monitoring.

## Troubleshooting

- **No BYD readings** — Check that Home Assistant can reach the battery’s web interface. Check the Home Assistant logs for timeouts or HTTP errors. HTTP 401 indicates that the battery rejected the request’s authentication.
- **No cell or module sensors** — Check that `cell_voltages: true` is set under `platform: byd_hv_box`, then restart Home Assistant.
- **Only one module appears** — Check the logs for module selection errors. Reading the other modules requires the firmware to accept the module selection request.
- **A diagnostic sensor is missing** — Check whether the corresponding field is present on the **Run Data** page for that module. The integration discovers sensors from the fields it can read.
- **Values look rounded** — Check the entity’s display precision in Home Assistant. A manual setting overrides the integration’s default.
- **Changes do not appear after replacing `sensor.py`** — Restart Home Assistant to load the updated Python code.

## Credits

This project continues the [original Home Assistant integration by Kai Schmid](https://github.com/kai-schmid/byd_hv_box), which is based on [Kilian Knoll’s original script](https://www.photovoltaikforum.com/thread/129771-byd-batteriespeicher-daten-programmatisch-auslesen/).

## License and disclaimer

This project is licensed under the GNU General Public License, version 3 or, at your option, any later version. See [LICENSE](LICENSE) for the full terms. The software is provided without warranty. Use it at your own risk.
