try:
    import smbus
except ImportError:
    smbus = None

from .register_state import RegisterState

__all__ = ['I2CRegisterState']


class I2CRegisterState(RegisterState):
    def __init__(self, registers, register_size):
        if smbus is None:
            raise ImportError('smbus not present, cannot use I2CRegisterState')
            
        super().__init__(registers, register_size)
        raise NotImplementedError

    def _read_register(self, address):
        raise NotImplementedError

    def _write_register(self, address, value):
        raise NotImplementedError
