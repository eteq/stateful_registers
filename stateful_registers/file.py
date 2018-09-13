try:
    import smbus
except ImportError:
    smbus = None

from .register_state import RegisterState

__all__ = ['FileRegisterState']


class FileRegisterState(RegisterState):
    """
    A `RegisterState` that is recorded in a file.

    Parameters
    ----------
    infn : str
        Readable file to use as the input
    outfn : str
        Writeable file to use as the output, if None, means use the same as ``infn``.
    update : bool
        If True, read/write the file whenever the register is accessed, if
        False waits for an explicit `read_file` `write_file` call.
    hex : bool
        If True, the file is in hex, if False, assume decimal
    """
    def __init__(self, registers, infn, outfn=None, update=False, hex=True,
                 register_size=8):
        super().__init__(registers, register_size)
        self.infn = infn
        self.outfn = outfn
        self.update = update
        self.hex = True
        self._file_data = None

    def read_file(self):
        base = 16 if self.hex else 10

        self._file_data = {}
        with open(self.infn, 'r') as f:
            for l in f:
                if l.strip() == '':
                    continue

                ls = l.split()
                assert len(ls) == 2, 'Input file has row {} which is not two-element'.format(l)
                addr, val = ls

                self._file_data[int(addr, base=base)] = int(val, base=base)

    def write_file(self):
        if self._file_data is None:
            return

        if self.outfn is None:
            outfn = self.infn
        else:
            outfn = self.outfn

        with open(outfn, 'w') as f:
            for addr in sorted(self._file_data):
                if self.hex:
                    msg = '{:x} {:x}\n'
                else:
                    msg = '{} {}\n'
                f.write(msg.format(addr, self._file_data[addr]))

    def _read_register(self, address, ntimes=None):
        if self.update or self._file_data is None:
            self.read_file()

        if ntimes is None:
            return self._file_data[address]
        else:
            return [self._file_data[address+i] for i in range(ntimes)]

    def _write_register(self, address, value):
        self._file_data[address] = value
