"""Tests for pyhap.accessory_driver."""
import tempfile
from unittest.mock import MagicMock, patch
from uuid import uuid1

import pytest

from pyhap.accessory import STANDALONE_AID, Accessory
from pyhap.accessory_driver import AccessoryDriver
from pyhap.characteristic import (HAP_FORMAT_INT, HAP_PERMISSION_READ,
                                  PROP_FORMAT, PROP_PERMISSIONS,
                                  Characteristic)
from pyhap.const import HAP_REPR_IID, HAP_REPR_CHARS, HAP_REPR_AID, HAP_REPR_VALUE
from pyhap.service import Service

CHAR_PROPS = {
    PROP_FORMAT: HAP_FORMAT_INT,
    PROP_PERMISSIONS: HAP_PERMISSION_READ,
}


@pytest.fixture
def driver():
    with patch('pyhap.accessory_driver.HAPServer'), \
        patch('pyhap.accessory_driver.Zeroconf'), \
            patch('pyhap.accessory_driver.AccessoryDriver.persist'):
        yield AccessoryDriver()


def test_auto_add_aid_mac(driver):
    acc = Accessory(driver, 'Test Accessory')
    driver.add_accessory(acc)
    assert acc.aid == STANDALONE_AID
    assert driver.state.mac is not None


def test_not_standalone_aid(driver):
    acc = Accessory(driver, 'Test Accessory', aid=STANDALONE_AID + 1)
    with pytest.raises(ValueError):
        driver.add_accessory(acc)


def test_persist_load():
    with tempfile.NamedTemporaryFile(mode='r+') as file:
        with patch('pyhap.accessory_driver.HAPServer'), \
                patch('pyhap.accessory_driver.Zeroconf'):
            driver = AccessoryDriver(port=51234, persist_file=file.name)
            driver.persist()
            pk = driver.state.public_key
            # Re-start driver with a "new" accessory. State gets loaded into
            # the new accessory.
            driver = AccessoryDriver(port=51234, persist_file=file.name)
            driver.load()
    assert driver.state.public_key == pk


def test_service_callbacks(driver):
    acc = Accessory(driver, 'TestAcc')

    service = Service(uuid1(), 'Lightbulb')
    char_on = Characteristic('On', uuid1(), CHAR_PROPS)
    char_brightness = Characteristic('Brightness', uuid1(), CHAR_PROPS)

    service.add_characteristic(char_on)
    service.add_characteristic(char_brightness)

    mock_callback = MagicMock()
    service.setter_callback = mock_callback

    acc.add_service(service)
    driver.add_accessory(acc)

    char_on_iid = char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = char_brightness.to_HAP()[HAP_REPR_IID]

    driver.set_characteristics({
        HAP_REPR_CHARS: [{
            HAP_REPR_AID: acc.aid,
            HAP_REPR_IID: char_on_iid,
            HAP_REPR_VALUE: True
        }, {
            HAP_REPR_AID: acc.aid,
            HAP_REPR_IID: char_brightness_iid,
            HAP_REPR_VALUE: 88
        }]
    }, "mock_addr")

    mock_callback.assert_called_with({'On': True, 'Brightness': 88})


def test_start_stop_sync_acc(driver):
    class Acc(Accessory):
        running = True

        @Accessory.run_at_interval(0)
        def run(self):
            self.running = False
            driver.stop()

        def setup_message(self):
            pass

    acc = Acc(driver, 'TestAcc')
    driver.add_accessory(acc)
    driver.start()
    assert not acc.running


def test_start_stop_async_acc(driver):
    class Acc(Accessory):

        @Accessory.run_at_interval(0)
        async def run(self):
            driver.stop()

        def setup_message(self):
            pass

    acc = Acc(driver, 'TestAcc')
    driver.add_accessory(acc)
    driver.start()
    assert driver.loop.is_closed()


def test_send_events(driver):
    class LoopMock():
        runcount = 0

        def is_closed(self):
            self.runcount += 1
            if self.runcount > 1:
                return True
            return False

    class HapServerMock():
        pushed_events = []

        def push_event(self, bytedata, client_addr):
            self.pushed_events.extend([[bytedata, client_addr]])
            return 1

        def get_pushed_events(self):
            return self.pushed_events

    driver.http_server = HapServerMock()
    driver.loop = LoopMock()
    driver.topics = {"mocktopic": ["client1", "client2", "client3"]}
    driver.event_queue.put(("mocktopic", "bytedata", "client1"))
    driver.send_events()

    # Only client2 and client3 get the event when client1 sent it
    assert (driver.http_server.get_pushed_events() ==
            [["bytedata", "client2"], ["bytedata", "client3"]])
