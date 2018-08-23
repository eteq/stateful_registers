"""
A module for storing the register state of some peripheral.

The expectation is typically to subclass RegisterState with a new initializer
that overrides most of the initializer's keywords with whatever the correct
options are for the specific peripheral.
"""
import copy

from abc import ABC, abstractmethod
from collections import defaultdict, OrderedDict

__all__ = ['RegisterState', 'RegisterValue', 'MultiRegisterValue']


class RegisterValue:
    def __init__(self, name, address, offset=0, nbits=1,
                       description='', writeable=None):
        """
        name : str
            Name of the register value
        address : int
            Address of the register
        offset : int
            Bit-offset within the word to the *start* of the value
        nbits : int
            Number of bits in this value
        description : str
            A human-readable description
        writeable : bool or None
            Whether the value is writeable, or None for "unspecified"
            (effectively writeable but need to check after)
        """
        self.name = name
        self.address = address
        self.offset = offset
        self.nbits = nbits
        self.description = description
        self.writeable = writeable
        self._value = None

    _infofields = ('name', 'address', 'offset', 'nbits', 'writeable',
                   'description')
    def __repr__(self):
        infostr = ', '.join(['{}={}'.format(nm, repr(getattr(self, nm))) for nm in self._infofields])
        return '<RegisterValue at {} : {}>'.format(hex(id(self)), infostr)

    def copy(self):
        return copy.copy(self)

    @property
    def bitmask(self):
        return 2**self.nbits - 1 << self.offset

    @property
    def register_value(self):
        return self._value << self.offset

    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, val):
        if val >= 2**self.nbits:
            raise ValueError('Value {} does not fit into {} bits (register '
                             'value {})'.format(val, self.nbits, self.name))
        self._value = val


class MultiRegisterValue:
    """
    name : str
        Name of the register value
    registers : list of RegisterValues
        The individual registers, from least to most significant bits
    description : str
        A human-readable description
    """
    def __init__(self, name, registers, description=''):
        """
        name :
        """
        self.name = name
        self.registers = tuple(registers)
        self.description = description

        for r in self.registers:
            if not isinstance(r, RegisterValue):
                raise TypeError('registers in MultiRegisterValue must be RegisterValues')

    @property
    def value(self):
        val = 0
        bitsdone = 0
        for r in self.registers:
            val |= r.value << bitsdone
            bitsdone += r.nbits
        return val
    @value.setter
    def value(self, val):
        raise NotImplementedError

    def copy(self):
        return copy.copy(self)


class RegisterState(ABC):
    def __init__(self, registers, register_size=8):
        self._register_size = register_size
        self._update_registers(registers)

    def _update_registers(self, regs):
        self._name_to_reg = {r.name: r.copy() for r in regs
                             if not isinstance(r, MultiRegisterValue)}

        # create the MultiRegisterValue's but re-link them to the *copied*
        # registers created above
        self._name_to_multireg = {r.name: r.copy() for r in regs
                                  if isinstance(r, MultiRegisterValue)}
        for mr in self._name_to_multireg.values():
            mr.registers = tuple((self._name_to_reg[r.name] for r in mr.registers))

        addr_to_regs_temp = defaultdict(list)
        for r in self._name_to_reg.values():
            addr_to_regs_temp[r.address].append(r)
        self._addr_to_regs = a2r = OrderedDict()
        for addr in addr_to_regs_temp:
            addr_to_regs_temp[addr].sort(key=lambda val: val.offset)
            a2r[addr] = regs = tuple(addr_to_regs_temp[addr])

            # validate that there are no overlapping register words
            bits_set = 0
            for reg in regs:
                if reg.bitmask & bits_set != 0:
                    raise ValueError('Registers overlap in address '
                                     '{}: {}'.format(addr, regs))
                bits_set |= reg.bitmask
            if bits_set >= 2**self.register_size:
                raise ValueError('Register values go past the word size in address {}: {}'.format(addr, regs))

    def get_register(self, name):
        if name in self._name_to_multireg:
            return self._name_to_multireg[name]
        else:
            return self._name_to_reg[name]

    def get_registers_at_address(self, address):
        return self._addr_to_regs[address]

    @property
    def register_names(self):
        return tuple(self._name_to_reg.keys())

    @property
    def register_size(self):
        return self._register_size

    def _read_raw(self, registers, groupread):
        if registers is None:
            addrs = self._addr_to_regs.keys()
        else:
            addrs = sorted(set([reg.address for reg in registers]))
        if groupread:
            minaddr = min(addrs)
            vals = self._read_register(minaddr, ntimes=max(addrs) - minaddr + 1)
            return {(minaddr + i): v for i, v in enumerate(vals)}
        else:
            return {addr: self._read_register(addr) for addr in addrs}

    def read_state(self, registers=None, groupread='multi', update_all=True):
        """
        Updates the state from the device.  If ```registers` is None, update all
        registers, otherwise should be a list of registers, and only addresses
        from that register will be.

        If ``groupread`` is True, lump the reads into one call.  If 'multi',
        only group the reads that are MultiRegisterValue's.

        If ``update_all`` is True, this updates everything that was read even if
        it wasn't specifically asked for.  If False, only ``registers`` are
        updated.
        """

        # convert any MultiRegisterValue's to their constituent registers
        if registers is not None:
            registers = list(registers)
            mr_idxs = [i for i, r in enumerate(registers)
                       if isinstance(i, MultiRegisterValue)]
            for i in mr_idxs[::-1]:
                mr = registers.pop(i)
                registers.extend(mr.registers)
            registers = set(registers)

        if groupread == 'multi':
            raw_values = self.read_state(registers=registers, groupread=False,
                                         update_all=update_all)
            for mr in self._name_to_multireg.values():
                regs_to_up = [reg for reg in mr.registers if reg in registers]
                raw_values.update(self.read_state(regs_to_up, groupread=True,
                                                  update_all=update_all))
        else:
            raw_values = self._read_raw(registers, groupread)
            r2c = registers if update_all else None
            for addr, rawval in raw_values.items():
                self._update_state_by_register(addr, rawval, regs_to_check=r2c)
        return raw_values

    def _update_state_by_register(self, addr, val, skip_writeable=False,
                                  regs_to_check=None):
        """
        regs_to_check of None means check everything, otherwise it's a list of
        register objects.
        """
        for regv in self._addr_to_regs[addr]:
            if skip_writeable and regv.writeable:
                continue
            if regs_to_check is not None and regv not in regs_to_check:
                continue
            regv.value = (val & regv.bitmask) >> regv.offset

    def write_state(self, registers=None, only_update=True):
        raw_values = None
        if only_update:
            raw_values = self._read_raw()
        if registers is None:
            addrs = self._addr_to_regs.keys()
        else:
            addrs = [reg.address for reg in registers]

        # for each address, build the expected value from the corresponding registers
        for addr in addrs:
            newval = raw_values[addr] if only_update else 0
            read_back = False
            for regv in self._addr_to_regs[addr]:
                if regv.value is None:
                    continue
                if regv.writeable is None:
                    read_back = True
                elif not regv.writeable:
                    continue

                # set everythink at the bitmask to 0
                newval &= ~regv.bitmask&(2**self._register_size - 1)
                if regv.value != 0:
                    newval |= regv.value << regv.offset

                if not only_update or newval != raw_values[addr]:
                    self._write_register(addr, newval)
            if read_back:
                rval = self._read_register(addr)
                self._update_state_by_register(addr, rval, skip_writeable=True)

    @abstractmethod
    def _read_register(self, address, ntimes=None):
        """
        Reads a single register.  If ``ntimes`` is None the single value,
        otherwise continues reading until `ntimes` words have been read
        """
        raise NotImplementedError

    @abstractmethod
    def _write_register(self, address, value):
        """
        Writes to a register.  ``value`` could be a list, which means write in a
        single operation
        """
        raise NotImplementedError
