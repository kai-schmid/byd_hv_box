# BYD HV BOX Home Assistant Integration

This Home Assistant custom component allows you to integrate your BYD HV BOX into Home Assistant, enabling you to monitor various parameters such as voltage, current, state of charge, and more.

## Original Author

This component is based on the original code by Kilian Knoll. The original script can be found [here](https://www.photovoltaikforum.com/thread/129771-byd-batteriespeicher-daten-programmatisch-auslesen/).

## Installation

### Step 1: Download the Custom Component

1. Download the custom component files and place them in your Home Assistant configuration directory under `custom_components/byd_hv_box/`.

### Step 2: Directory Structure

Ensure your directory structure looks like this:  
```
homeassistant/  
|-- custom_components/
|--|-- byd_hv_box/
|--|-- init.py
|--|-- manifest.json
|--|-- sensor.py
```
Replace YOUR_BYD_BOX_IP, YOUR_USERNAME, and YOUR_PASSWORD with your actual BYD HV BOX IP address, username, and password.
### Step 4: Restart Home Assistant

Restart your Home Assistant instance to load the new custom component.
Sensor Entities

Configuration in configuration.yaml:

### Step 3: Configuration

Add the following configuration to your `configuration.yaml` file:

```yaml
sensor:
  - platform: byd_hv_box
    host: YOUR_BYD_BOX_IP
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
```


The component will create sensor entities for the following parameters:

    Array Voltage (V)
    Pack Voltage (V)
    Current (A)
    State of Charge (%)
    System Temperature (°C)
    Max Cell Voltage (V)
    Min Cell Voltage (V)
    Max Cell Temperature (°C)
    Min Cell Temperature (°C)
    Max Voltage Position
    Min Voltage Position
    Max Temperature Position
    Min Temperature Position
    Power (W)
    Total Charge Energy (kWh)
    Total Discharge Energy (kWh)
    Total Cycle Counts

# Troubleshooting

If you encounter issues or errors, check the Home Assistant logs for more details. Make sure the BYD HV BOX is accessible from the network and that the provided credentials are correct.
License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see http://www.gnu.org/licenses/.
# Disclaimer

Please note that any incorrect or careless usage of this module as well as errors in the implementation can damage your BYD box! Therefore, the author does not provide any guarantee or warranty concerning to correctness, functionality or performance and does not accept any liability for damage caused by this module, examples or mentioned information. Thus, use it at your own risk!
