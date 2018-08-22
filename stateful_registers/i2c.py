try:
    import smbus
except ImportError:
    smbus = None

from .register_state import RegisterState

__all__ = ['I2CRegisterState']


class I2CRegisterState(RegisterState):
    def __init__(self, registers, device_address, i2c_bus=1, register_size=8,
             write_bit=7):
        if smbus is None:
            raise ImportError('smbus not present, cannot use I2CRegisterState')

        super().__init__(registers, register_size)
        self.bus = smbus.SMBus(i2c_bus)
        self.device_address = device_address

    @property
    def device_address(self):
        return self._device_address
    @device_address.setter
    def device_address(self, val):
        if not isinstance(val, int):
            raise TypeError('device_address must be an int')
        self._device_address = val

    def _read_register(self, address):
        return self.bus.read_byte_data(self._device_address, address)

    def _write_register(self, address, value):
        self.bus.write_byte_data(self._device_address, address, value)
