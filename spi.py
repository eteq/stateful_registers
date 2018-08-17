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

    def _read_register(self, address, ntimes=None):
        read_word = address & self._read_bitmask_and
        if ntimes is None:
            return self.spi.xfer([read_word, 0])[1]
        else:
            return self.spi.xfer2([read_word] + [0]*ntimes)[1:]

    def _write_register(self, address, value):
        if isinstance(value, int):
            self.spi.xfer([address | self._write_bitmask_or, value])
        else:
            # assume multi-write
            self.spi.xfer2([address | self._write_bitmask_or] + value)
