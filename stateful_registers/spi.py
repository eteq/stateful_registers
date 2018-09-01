try:
    import spidev
except ImportError:
    spidev = None

from .register_state import RegisterState

__all__ = ['SPIRegisterState']


class SPIRegisterState(RegisterState):
    """
    write_bit : int
        The bit to set to indicate a write operation. A read operation will have
        this bit unset. (swap set/unset if ``write_set`` is False)
    write_set : bool
        If true, ``write_bit`` is set for write and unset for read.  If False,
        it is unset for write and set for read.
    max_speed_hz : int or None
        The speed of the SPI bus or None to use default
    """
    def __init__(self, registers, spi_bus, spi_device, register_size=8,
                 write_bit=7, write_set=True, max_speed_hz=None):
        if spidev is None:
            raise ImportError('spidev not present, cannot use SPIRegisterState')

        super().__init__(registers, register_size)

        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        if max_speed_hz is not None:
            self.spi.max_speed_hz = max_speed_hz

        # setting _write_bit via the private variable so that _set_readwriteaddr
        # will work correctly when write_set is set
        self._write_bit = write_bit
        self.write_set = write_set

    def _read_register(self, address, ntimes=None):
        if ntimes is None:
            return self.spi.xfer([self._read_command(address), 0])[1]
        else:
            return self.spi.xfer2([self._read_command(address)] + [0]*ntimes)[1:]

    def _write_register(self, address, value):
        if isinstance(value, int):
            self.spi.xfer([self._write_command(address), value])
        else:
            # assume multi-write
            self.spi.xfer2([self._write_command(address)] + value)

    @property
    def write_bit(self):
        return self._write_bit
    @write_bit.setter
    def write_bit(self, val):
        self._write_bit = val
        self._set_readwriteaddr()

    @property
    def write_set(self):
        return self._write_set
    @write_set.setter
    def write_set(self, val):
        self._write_set = val
        self._set_readwriteaddr()

    def _set_readwriteaddr(self):
        bit = 2**self.write_bit

        def setter(address):
            return address | bit

        def unsetter(address):
            return address & ~bit

        if self.write_set:
            self._read_command = unsetter
            self._write_command = setter
        else:
            self._read_command = setter
            self._write_command = unsetter
