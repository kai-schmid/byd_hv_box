import logging
import requests
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

DOMAIN = "byd_hv_box"
SENSOR_TYPES = {
    "arrayvoltage": ["Array Voltage", "V"],
    "packvoltage": ["Pack Voltage", "V"],
    "current": ["Current", "A"],
    "soc": ["State of Charge", "%"],
    "sysTemp": ["System Temperature", "°C"],
    "maxcellvol": ["Max Cell Voltage", "V"],
    "mincellvol": ["Min Cell Voltage", "V"],
    "maxcelltemp": ["Max Cell Temperature", "°C"],
    "mincelltemp": ["Min Cell Temperature", "°C"],
    "maxvolpos": ["Max Voltage Position", ""],
    "minvolpos": ["Min Voltage Position", ""],
    "maxtemppos": ["Max Temperature Position", ""],
    "mintemppos": ["Min Temperature Position", ""],
    "power": ["Power", "W"],
    "Total_Charge_Energy": ["Total Charge Energy", "kWh"],
    "Total_Discharge_Energy": ["Total Discharge Energy", "kWh"],
    "Total_Cycle_Counts": ["Total Cycle Counts", ""]
}

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the BYD HV BOX sensor."""
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    sensors = []
    for sensor_type in SENSOR_TYPES:
        sensors.append(BydHvBoxSensor(host, username, password, sensor_type))

    add_entities(sensors, True)

class BydHvBoxSensor(SensorEntity):
    """Representation of a BYD HV BOX sensor."""

    def __init__(self, host, username, password, sensor_type):
        """Initialize the sensor."""
        self._host = host
        self._username = username
        self._password = password
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._state = None
        self._data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    def update(self):
        """Fetch new state data for the sensor."""
        self._data = self.readbyd()
        if self._data:
            self._state = self._data.get(self.type)

    def readbyd(self):
        """Query data from the BYD HV BOX."""
        try:
            session = requests.Session()
            url = f'http://{self._host}/asp/RunData.asp'
            response = session.get(url, auth=HTTPBasicAuth(self._username, self._password))
            if response.status_code == 200:
                page = response.text
                soup = BeautifulSoup(page, 'html.parser')
                soup_ele = soup.body.form.table
                soup_reduced = soup_ele.find_all('input', attrs={"type": "text"})
                keyvalue = [elem['value'] for elem in soup_reduced]

                byd_data = {
                    "arrayvoltage": float(keyvalue[0]),
                    "packvoltage": float(keyvalue[1]),
                    "current": float(keyvalue[2]),
                    "soc": keyvalue[3],
                    "sysTemp": keyvalue[4],
                    "maxcellvol": float(keyvalue[5]),
                    "mincellvol": float(keyvalue[6]),
                    "maxcelltemp": float(keyvalue[7]),
                    "mincelltemp": float(keyvalue[8]),
                    "maxvolpos": int(keyvalue[9]),
                    "minvolpos": keyvalue[10],
                    "maxtemppos": keyvalue[11],
                    "mintemppos": keyvalue[12],
                    "power": keyvalue[13]
                }

                url = f'http://{self._host}/asp/StatisticInformation.asp'
                response = session.get(url, auth=HTTPBasicAuth(self._username, self._password))
                if response.status_code == 200:
                    page = response.text
                    soup = BeautifulSoup(page, 'html.parser')
                    soup_ele = soup.body.table

                    total_charge_energy = soup_ele.find("td", text="Total Charge Energy:").find_next_sibling("td").text
                    total_charge_energy = float(total_charge_energy.split()[0])
                    byd_data["Total_Charge_Energy"] = total_charge_energy

                    total_discharge_energy = soup_ele.find("td", text="Total Discharge Energy:").find_next_sibling("td").text
                    total_discharge_energy = float(total_discharge_energy.split()[0])
                    byd_data["Total_Discharge_Energy"] = total_discharge_energy

                    total_cycle_counts = soup_ele.find("td", text="Total Cycle Counts:").find_next_sibling("td").text
                    byd_data["Total_Cycle_Counts"] = float(total_cycle_counts)

                return byd_data
            else:
                _LOGGER.error(f"Failed to connect to BYD HV BOX: {response.status_code}")
        except Exception as e:
            _LOGGER.error(f"Error fetching data from BYD HV BOX: {e}")
        return None