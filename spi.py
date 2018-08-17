from .register_state import RegisterState

__all__ = ['SPIRegisterState']

class SPIRegisterState(RegisterState):
    def __init__(self, registers, register_size):
        super().__init__(registers, register_size)
        raise NotImplementedError

    def _read_register(self, address):
        raise NotImplementedError

    def _write_register(self, address, value):
        raise NotImplementedError
