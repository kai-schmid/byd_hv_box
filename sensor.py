"""Read the legacy BYD Battery-Box HV web interface."""

from datetime import timedelta
import logging
from math import isfinite
import re

from bs4 import BeautifulSoup
import requests
from requests.auth import HTTPBasicAuth
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "byd_hv_box"
UPDATE_INTERVAL = timedelta(seconds=60)
HTTP_TIMEOUT = (3, 4)  # Connect and read timeouts, in seconds.
RUN_PAGE = "RunData.asp"
STATISTICS_PAGE = "StatisticInformation.asp"
CONF_CELL_VOLTAGES = "cell_voltages"
CELL_DATA = CONF_CELL_VOLTAGES
CELL_LABEL = re.compile(r"CellVol\[([1-9][0-9]*)\]:?", re.I)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CELL_VOLTAGES, default=False): cv.boolean,
    }
)


def _sensor(
    key, name, unit=None, device_class=None, state_class=SensorStateClass.MEASUREMENT
):
    return SensorEntityDescription(
        key=key,
        name=f"BYD HV {name}",
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=state_class,
    )


RUN_SENSORS = (
    _sensor("arrayvoltage", "Array Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    _sensor("packvoltage", "Pack Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    _sensor("current", "Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT),
    _sensor("soc", "State of Charge", UnitOfRatio.PERCENTAGE, SensorDeviceClass.BATTERY),
    _sensor("sysTemp", "System Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    _sensor("maxcellvol", "Max Cell Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    _sensor("mincellvol", "Min Cell Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    _sensor("maxcelltemp", "Max Cell Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    _sensor("mincelltemp", "Min Cell Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    _sensor("maxvolpos", "Max Voltage Position", state_class=None),
    _sensor("minvolpos", "Min Voltage Position", state_class=None),
    _sensor("maxtemppos", "Max Temperature Position", state_class=None),
    _sensor("mintemppos", "Min Temperature Position", state_class=None),
    _sensor("power", "Power", UnitOfPower.WATT, SensorDeviceClass.POWER),
)
STATISTICS_SENSORS = (
    _sensor(
        "Total_Charge_Energy", "Total Charge Energy", UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING,
    ),
    _sensor(
        "Total_Discharge_Energy", "Total Discharge Energy", UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING,
    ),
    _sensor("Total_Cycle_Counts", "Total Cycle Counts", state_class=SensorStateClass.TOTAL_INCREASING),
)
POSITION_KEYS = {"maxvolpos", "minvolpos", "maxtemppos", "mintemppos"}
COUNT_KEYS = POSITION_KEYS | {"Total_Cycle_Counts"}
TOTAL_KEYS = {description.key for description in STATISTICS_SENSORS}
NUMBER = re.compile(r"([+-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+))\s*([^\d\s]*)")


def _label(text):
    """Normalize field names and visible labels without using input positions."""
    return re.sub(r"[^a-z0-9]", "", text.casefold())


RUN_FIELDS = {
    _label(label): description
    for description in RUN_SENSORS
    for label in (description.key, description.name.removeprefix("BYD HV "))
}
STATISTICS_FIELDS = {
    _label(description.key): description for description in STATISTICS_SENSORS
}


def _unit(text):
    return text.strip().casefold().replace("℃", "°c")


def _number(raw, description, row_unit=""):
    """Parse a single value, keeping the original native units."""
    match = NUMBER.fullmatch(raw.strip().replace("−", "-"))
    if match is None:
        return None

    number, suffix = match.groups()
    unit = _unit(suffix or row_unit)
    expected_unit = _unit(description.native_unit_of_measurement or "")
    value = float(number.replace(",", "."))
    key = description.key

    if key == "power":
        if unit == "kw":
            value *= 1000
        elif unit != expected_unit:
            return None
    elif key in TOTAL_KEYS and expected_unit == "kwh" and unit == "wh":
        value /= 1000
    elif unit and unit != expected_unit:
        return None

    if not isfinite(value) or (key in TOTAL_KEYS and value < 0):
        return None
    if key in COUNT_KEYS:
        return int(value) if value >= 0 and value.is_integer() else None
    return value


def _parse_run_data(html):
    soup = BeautifulSoup(html, "html.parser")
    # As in the original integration, read the first Run Data form table.
    table = soup.select_one("form table")
    if table is None:
        return {}

    data = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        for index, cell in enumerate(cells):
            field = cell.find("input", attrs={"type": re.compile("^text$", re.I)})
            if field is None:
                continue
            # The label may be in the value cell or in the preceding cell.
            cell_text = cell.get_text(" ", strip=True)
            description = RUN_FIELDS.get(_label(cell_text))
            row_unit = "" if description is not None else cell_text
            if description is None and index:
                description = RUN_FIELDS.get(_label(cells[index - 1].get_text(" ", strip=True)))
            if description is None:
                description = RUN_FIELDS.get(_label(field.get("name", "")))
            if description is None:
                description = RUN_FIELDS.get(_label(field.get("id", "")))
            if description is None:
                continue
            unit_cell = cell.find_next_sibling(["td", "th"])
            if not row_unit and unit_cell is not None and unit_cell.find("input") is None:
                row_unit = unit_cell.get_text(" ", strip=True)
                if _label(row_unit) in RUN_FIELDS:
                    row_unit = ""
            value = _number(field.get("value", ""), description, row_unit)
            if value is not None:
                data.setdefault(description.key, value)

    # Use contemporaneous DC measurements if the reported power has no unit.
    if "power" not in data and "packvoltage" in data and "current" in data:
        power = data["packvoltage"] * data["current"]
        if isfinite(power):
            data["power"] = round(power, 1)
    return data


def _selection(form, name):
    select = form.find("select", attrs={"name": name})
    if select is None:
        return None, []
    options = select.find_all("option", value=re.compile(r"^[1-9][0-9]*$"))
    selected = next((option for option in options if option.has_attr("selected")), None)
    values = list(dict.fromkeys(option["value"] for option in options))
    return selected["value"] if selected is not None else None, values


def _module_data(html):
    """Read the displayed module ID, available module IDs and cell voltages."""
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="RunData", action="/goform/SetRunData")
    if form is None:
        return None, None, [], {}
    array, _ = _selection(form, "ArrayNum")
    module, modules = _selection(form, "SeriesBatteryNum")
    cells = {}
    for cell in form.find_all("td"):
        match = CELL_LABEL.fullmatch(cell.get_text(" ", strip=True))
        if match is None:
            continue
        value_cell = cell.find_next_sibling("td")
        field = value_cell.find("input", attrs={"type": "text"}) if value_cell else None
        if field is None:
            continue
        value = _number(
            field.get("value", ""), RUN_FIELDS["maxcellvol"],
            value_cell.get_text(" ", strip=True),
        )
        if value is not None:
            cells[int(match[1])] = value
    return array, module, modules, cells


def _cell_values(array, module, cells):
    return {
        f"array_{int(array):02d}_module_{int(module):02d}_cell_{cell:02d}_voltage": value
        for cell, value in cells.items()
    }


def _parse_statistics(html):
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    for cell in soup.find_all(["td", "th"]):
        description = STATISTICS_FIELDS.get(_label(cell.get_text(" ", strip=True)))
        if description is None:
            continue
        value_cell = cell.find_next_sibling(["td", "th"])
        if value_cell is None:
            continue
        value = _number(value_cell.get_text(" ", strip=True), description)
        if value is not None:
            data.setdefault(description.key, value)
    return data


class BydCoordinator(DataUpdateCoordinator[dict[str, dict[str, float | int]]]):
    """Share one refresh of the system and optional cell readings."""

    def __init__(self, hass, host, username, password, add_cell_entities=None):
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=f"BYD HV BOX ({host})",
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self._base_url = f"http://{host}/asp/"
        self._selection_url = f"http://{host}/goform/SetRunData"
        self._auth = HTTPBasicAuth(username, password)
        self._last_errors = {}
        self._add_cell_entities = add_cell_entities
        self._known_cells = set()

    def _select_module(self, session, array, module):
        response = session.post(
            self._selection_url,
            data={"ArrayNum": array, "SeriesBatteryNum": module},
            timeout=HTTP_TIMEOUT,
            allow_redirects=False,
        )
        if response.status_code in (301, 302, 303):
            # Fetch the known read page instead of following an arbitrary redirect.
            response = session.get(
                self._base_url + RUN_PAGE, timeout=HTTP_TIMEOUT, allow_redirects=False
            )
        if response.status_code != 200:
            raise UpdateFailed(f"HTTP {response.status_code} beim Auswählen von Modul {module}")
        actual_array, actual_module, _, cells = _module_data(response.text)
        if (actual_array, actual_module) != (array, module):
            raise UpdateFailed(f"Antwort bestätigt Modul {module} in Array {array} nicht")
        return cells

    def _read_cells(self, session, html, errors):
        array, selected, modules, cells = _module_data(html)
        if array is None or selected is None:
            errors[CELL_DATA] = "Keine unterstützte Modulauswahl in Run Data gefunden"
            return {}

        values = _cell_values(array, selected, cells)
        attempted_selection = False
        try:
            for module in modules:
                if module == selected:
                    continue
                attempted_selection = True
                cells = self._select_module(session, array, module)
                if not cells:
                    raise UpdateFailed(f"Modul {module} liefert keine Zellspannungen")
                values.update(_cell_values(array, module, cells))
        except (requests.RequestException, UpdateFailed) as err:
            errors[CELL_DATA] = str(err) if isinstance(err, UpdateFailed) else type(err).__name__
        finally:
            if attempted_selection:
                try:
                    self._select_module(session, array, selected)
                except (requests.RequestException, UpdateFailed) as err:
                    detail = str(err) if isinstance(err, UpdateFailed) else type(err).__name__
                    errors["Modulauswahl"] = f"Ausgangsauswahl konnte nicht bestätigt werden ({detail})"
        if not values:
            errors.setdefault(CELL_DATA, "Keine Zellspannungen gefunden")
        return values

    def _read_pages(self):
        data = {}
        errors = {}
        run_html = None
        # Reuse one session for the entire refresh, including module selection.
        with requests.Session() as session:
            session.auth = self._auth
            for page, parser in (
                (RUN_PAGE, _parse_run_data),
                (STATISTICS_PAGE, _parse_statistics),
            ):
                try:
                    response = session.get(
                        self._base_url + page, timeout=HTTP_TIMEOUT, allow_redirects=False
                    )
                except requests.Timeout:
                    errors[page] = "Zeitüberschreitung beim Verbindungsaufbau oder Lesen"
                    continue
                except requests.RequestException as err:
                    errors[page] = f"HTTP-Anfrage fehlgeschlagen ({type(err).__name__})"
                    continue

                if response.status_code == 401:
                    challenge = response.headers.get("WWW-Authenticate", "")
                    schemes = sorted(set(re.findall(
                        r"(?:^|,)\s*(Basic|Digest|Bearer|Negotiate|NTLM)\b",
                        challenge,
                        re.I,
                    )))
                    advertised = ", ".join(schemes) if schemes else "kein bekanntes Verfahren"
                    errors[page] = (
                        f"HTTP 401 bei Basic-Authentifizierung "
                        f"(WWW-Authenticate: {advertised})"
                    )
                elif response.status_code != 200:
                    errors[page] = f"HTTP {response.status_code}"
                elif page_data := parser(response.text):
                    data[page] = page_data
                    if page == RUN_PAGE:
                        run_html = response.text
                else:
                    errors[page] = "HTTP 200 ohne erkennbare BYD-Messwerte (HTML oder Anmeldung prüfen)"
            if self._add_cell_entities is not None and run_html is not None:
                if cell_data := self._read_cells(session, run_html, errors):
                    data[CELL_DATA] = cell_data
        return data, errors

    def _async_refresh_finished(self):
        if self._add_cell_entities is None or not self.last_update_success:
            return
        new_keys = (self.data or {}).get(CELL_DATA, {}).keys() - self._known_cells
        if new_keys:
            self._known_cells.update(new_keys)
            self._add_cell_entities(sorted(new_keys))

    async def _async_update_data(self):
        data, errors = await self.hass.async_add_executor_job(self._read_pages)
        for page, error in errors.items():
            # HA logs the first total failure. Also report a new 401 if it is
            # already offline and therefore suppressing repeat update failures.
            if self._last_errors.get(page) != error and (
                data or (not self.last_update_success and error.startswith("HTTP 401"))
            ):
                _LOGGER.warning("%s: %s: %s", self.name, page, error)
        self._last_errors = errors
        if not data:
            raise UpdateFailed("; ".join(f"{page}: {error}" for page, error in errors.items()))
        return data


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the existing YAML sensor platform."""
    host = config[CONF_HOST]

    def add_cell_entities(keys):
        async_add_entities(
            BydHvBoxSensor(
                coordinator, host, CELL_DATA,
                _sensor(key, key.replace("_", " ").title(), UnitOfElectricPotential.VOLT,
                        SensorDeviceClass.VOLTAGE),
            )
            for key in keys
        )

    coordinator = BydCoordinator(
        hass, host, config[CONF_USERNAME], config[CONF_PASSWORD],
        add_cell_entities if config[CONF_CELL_VOLTAGES] else None,
    )
    async_add_entities(
        BydHvBoxSensor(coordinator, host, page, description)
        for page, descriptions in ((RUN_PAGE, RUN_SENSORS), (STATISTICS_PAGE, STATISTICS_SENSORS))
        for description in descriptions
    )
    # Start the first refresh without holding up YAML platform setup.
    hass.async_create_background_task(coordinator.async_refresh(), f"{coordinator.name} initial refresh")


class BydHvBoxSensor(CoordinatorEntity[BydCoordinator], SensorEntity):
    """Expose one field from the shared snapshot."""

    def __init__(self, coordinator, host, page, description):
        super().__init__(coordinator)
        self._page = page
        self.entity_description = description
        self._attr_unique_id = f"{host}_{description.key}"
        if description.native_unit_of_measurement in (
            UnitOfElectricPotential.VOLT,
            UnitOfElectricCurrent.AMPERE,
            UnitOfEnergy.KILO_WATT_HOUR,
        ):
            self._attr_suggested_display_precision = 3

    @property
    def available(self):
        if not super().available:
            return False
        page = (self.coordinator.data or {}).get(self._page)
        return page is not None and (
            self._page != CELL_DATA or self.entity_description.key in page
        )

    @property
    def native_value(self):
        if self.available:
            return self.coordinator.data[self._page].get(self.entity_description.key)
        return None

