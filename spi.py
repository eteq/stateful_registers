import spidev

from .register_state import RegisterState

__all__ = ['SPIRegisterState']


class SPIRegisterState(RegisterState):
    """
    write_bit : int
        the bit to set to indicate a write operation.  If negative, setting the
        bit means read.
    """
    def __init__(self, registers, spi_bus, spi_device, register_size=8,
                 write_bit=7):
        super().__init__(registers, register_size)
        self.write_bit = write_bit

        self._read_bitmask_and = ~(2**self.write_bit) & 2**self.register_size-1
        self._write_bitmask_or = 2**self.write_bit

        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)

    def _read_register(self, address):
        return self.spi.xfer([address & self._read_bitmask_and, 0])[1]

    def _write_register(self, address, value):
        self.spi.xfer([address | self._write_bitmask_or, value])
