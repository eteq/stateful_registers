"""
A module for storing the register state of some peripheral.

The expectation is typically to subclass RegisterState with a new initializer
that overrides most of the initializer's keywords with whatever the correct
options are for the specific peripheral.
"""
import copy

from abc import ABC, abstractmethod
from collections import defaultdict

__all__ = ['RegisterState', 'RegisterValue']


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
        infostr = ', '.join(['{}='.format(nm, getattr(self, nm)) for nm in self._infofields])
        return '<RegisterValue at {: {}>'.format(hex(id(self)), infostr)

    def copy(self):
        return copy.copy(self)

    def bitmask(self):
        return 2**self.nbytes - 1 << self.offset

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
            mr.registers = (mr._name_to_reg[r.name] for r in mr.registers)

        addr_to_regs_temp = defaultdict(list)
        for r in self._name_to_reg.values():
            addr_to_regs_temp[r.address].append(r)
        self._addr_to_regs = a2r = {}
        for addr in addr_to_regs_temp:
            addr_to_regs_temp[addr].sort(lambda val: val.offset)
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
        return self._name_to_reg[name]

    def get_registers_at_address(self, address):
        return self._addr_to_regs[address]

    @property
    def register_size(self):
        return self._register_size

    def _read_raw(self):
        return {addr: self._read_register(addr) for addr in self._addr_to_regs}

    def read_state(self):
        raw_values = self._read_raw()
        for addr, rawval in raw_values.items():
            for regv in self._addr_to_regs[addr]:
                regv.value = (rawval & regv.bitmask) >> regv.nbits
        return raw_values

    def write_state(self, only_update=True):
        raw_values = None
        if only_updates:
            raw_values = self._read_raw()

        # for each address, build the expected value from the corresponding registers
        for addr in self._addr_to_regs:
            newval = raw_values[addr] if only_update else 0
            for regv in self._addr_to_regs[addr]:
                newval &= ~regv.bitmask&(2**self._register_size - 1)
                newval |= regv.value << self.offset

                if not only_update or newval != raw_values[addr]:
                    self._write_register(addr, newval)

    @abstractmethod
    def _read_register(self, address):
        """
        Reads a single register
        """
        raise NotImplementedError

    @abstractmethod
    def _write_register(self, address, value):
        """
        Writes to a register.  ``value`` could be a list, which means write to
        multiple consecutive registers
        """
        raise NotImplementedError
