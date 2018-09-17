"""
Example stateful register representation of a BME280 environment sensor
"""

from stateful_registers import (RegisterValue, MultiRegisterValue,
                                SPIRegisterState, I2CRegisterState)


class BME280BaseRegisterState:
    def __init__(self, **kwargs):
        kwargs.setdefault('registers', self.BME280_REGISTERS)
        self._rh_to_dewpoint = _rh_to_dewpoint_magnus
        super().__init__(**kwargs)

    BME280_REGISTERS = [
        RegisterValue('hum_lsb', 0xFE, nbits=8, writeable=False),
        RegisterValue('hum_msb', 0xFD, nbits=8, writeable=False),
        RegisterValue('temp_xlsb', 0xFC, offset=4, nbits=4, writeable=False),
        RegisterValue('temp_lsb', 0xFB, nbits=8, writeable=False),
        RegisterValue('temp_msb', 0xFA, nbits=8, writeable=False),
        RegisterValue('press_xlsb', 0xF9, offset=4, nbits=4, writeable=False),
        RegisterValue('press_lsb', 0xF8, nbits=8, writeable=False),
        RegisterValue('press_msb', 0xF7, nbits=8, writeable=False),
        RegisterValue('spi3w_en', 0xF5, offset=0, nbits=1, writeable=True),
        RegisterValue('filter', 0xF5, offset=2, nbits=3, writeable=True),
        RegisterValue('t_sb', 0xF5, offset=5, nbits=3, writeable=True),
        RegisterValue('mode', 0xF4, offset=0, nbits=2, writeable=True),
        RegisterValue('osrs_p', 0xF4, offset=2, nbits=3, writeable=True),
        RegisterValue('osrs_t', 0xF4, offset=5, nbits=3, writeable=True),
        RegisterValue('measuring', 0xF3, offset=0, nbits=1, writeable=False),
        RegisterValue('im_update', 0xF3, offset=3, nbits=1, writeable=False),
        RegisterValue('osrs_h', 0xF2, offset=0, nbits=3, writeable=True),
        RegisterValue('reset', 0xE0, offset=0, nbits=8, writeable=True),
        RegisterValue('id', 0xD0, offset=0, nbits=8, writeable=False),
    ]
    BME280_REGISTERS += [
        MultiRegisterValue('hum', BME280_REGISTERS[:2]),
        MultiRegisterValue('temp', BME280_REGISTERS[2:5]),
        MultiRegisterValue('press', BME280_REGISTERS[5:8]),
    ]
    BME280_REGISTERS += [RegisterValue('calib{:02}'.format(i), 0x88 + i,
                                       nbits=8, writeable=False)
                         for i in range(26)]
    BME280_REGISTERS += [RegisterValue('calib{:02}'.format(i), 0xE1 + i - 26,
                                       nbits=8, writeable=False)
                         for i in range(26, 42)]

    def read_env(self, tunit='F', punit='Pa', hunit='%'):
        """
        Reads and returns the calibrated (temp, pressure, humidity) tuple

        `tunit` can be 'F', 'C', or 'K'
        `punit` can be 'Pa', 'atm', 'mmHg', or 'inHg'
        `hunit` can be '%' (relatve), 'C', 'F', or 'K' (dewpoint)
        """
        env_regs = (self._name_to_multireg['temp'],
                    self._name_to_multireg['press'],
                    self._name_to_multireg['hum'])
        self.read_state(env_regs, groupread=True)

        self._update_calibs()

        # internal units are C, Pa, perc
        t, t_fine = self._compensate_temp(env_regs[0].value)
        p = self._compensate_press(env_regs[1].value, t_fine)
        h = self._compensate_hum(env_regs[2].value, t_fine)

        t = self._convert_t(t, tunit)
        p = self._convert_p(p, punit)
        h = self._convert_h(h, hunit, t)

        return t, p, h

    def _update_calibs(self):
        def calib_u16(calibnum0, swap=False, shift1=8):
            """
            The "weird" ones are [3:0], [11:4]
            """
            c0 = self.get_register('calib{:02}'.format(calibnum0)).value
            c1 = self.get_register('calib{:02}'.format(calibnum0+1)).value
            if swap:
                c0, c1 = c1, c0
            return c0 + (c1 << shift1)

        def calib_s16(calibnum0, swap=False, shift1=8):
            cal = calib_u16(calibnum0, swap, shift1)
            if cal > 32767:
                cal -= 65536
            return cal

        def calib_u8(calibnum0):
            return self.get_register('calib'+str(calibnum0)).value

        def calib_s8(calibnum0):
            cal = calib_u8(calibnum0)
            if cal > 127:
                cal -= 256
            return cal

        self._calib = {}
        self._calib['T1'] = calib_u16(0)
        self._calib['T2'] = calib_s16(2)
        self._calib['T3'] = calib_s16(4)

        self._calib['P1'] = calib_u16(6)
        self._calib['P2'] = calib_s16(8)
        self._calib['P3'] = calib_s16(10)
        self._calib['P4'] = calib_s16(12)
        self._calib['P5'] = calib_s16(14)
        self._calib['P6'] = calib_s16(16)
        self._calib['P7'] = calib_s16(18)
        self._calib['P8'] = calib_s16(20)
        self._calib['P9'] = calib_s16(22)

        self._calib['H1'] = calib_u8(25)
        self._calib['H2'] = calib_s16(26)
        self._calib['H3'] = calib_u8(28)
        self._calib['H4'] = calib_s16(29, True, shift1=4)
        self._calib['H5'] = calib_s16(30, shift1=4)
        self._calib['H6'] = calib_s8(32)

    def _compensate_temp(self, adc_t):
        """
        Returns t_true, t_fine where the former is in deg C and the latter is
        for _compensate_press
        """
        dig_T1, dig_T2, dig_T3 = (self._calib['T'+str(i+1)] for i in range(3))

        var1 = (adc_t/16384.0 - dig_T1/1024.) * dig_T2
        var2 = ((adc_t/131072.0 - dig_T1/8192.0) * (adc_t/131072.0 - dig_T1/8192.0)) * dig_T3

        t_fine = var1 + var2
        t_true = t_fine / 5120.0
        return t_true, t_fine

    def _compensate_press(self, adc_p, t_fine):
        dig_P1, dig_P2, dig_P3 = (self._calib['P'+str(i+1)] for i in range(3))
        dig_P4, dig_P5, dig_P6 = (self._calib['P'+str(i+4)] for i in range(3))
        dig_P7, dig_P8, dig_P9 = (self._calib['P'+str(i+7)] for i in range(3))

        var1 = (t_fine/2.0) - 64000.0
        var2 = var1 * var1 * dig_P6 / 32768.0
        var2 = var2 + var1 * dig_P5 * 2.0
        var2 = (var2/4.0)+(dig_P4 * 65536.0)
        var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0)*dig_P1
        if (var1 == 0.0):
            return 0  # avoid exception caused by division by zero

        p = 1048576.0 - adc_p
        p = (p - (var2 / 4096.0)) * 6250.0 / var1
        var1 = dig_P9 * p * p / 2147483648.0
        var2 = p * dig_P8 / 32768.0
        return p + (var1 + var2 + dig_P7) / 16.0

    def _compensate_hum(self, adc_h, t_fine):
        dig_H1, dig_H2, dig_H3 = (self._calib['H'+str(i+1)] for i in range(3))
        dig_H4, dig_H5, dig_H6 = (self._calib['H'+str(i+4)] for i in range(3))

        var_H = t_fine - 76800.0
        var_H = ((adc_h - (dig_H4 * 64.0 + dig_H5 / 16384.0 * var_H)) *
                 (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * var_H *
                 (1.0 + dig_H3 / 67108864.0 * var_H))))
        var_H = var_H * (1.0 - dig_H1 * var_H / 524288.0)

        if (var_H > 100.0):
            return 100.0
        elif (var_H < 0.0):
            return 0.0
        else:
            return var_H

    def _convert_t(self, t, tunit):
        if tunit == 'C':
            return t
        elif tunit == 'F':
            return t * 1.8 + 32
        elif tunit == 'K':
            return t - 273.15
        else:
            raise NotImplementedError("Unrecognized temp unit {}".format(tunit))

    def _convert_p(self, p, punit):
        if punit == 'Pa':
            return p
        elif punit == 'atm':
            return p * 0.00000986923267
        elif punit == 'mmHg':
            return p / 133.322387415
        elif punit == 'inHg':
            return p / 3386.389
        else:
            raise NotImplementedError("Unrecognized pressure unit {}".format(punit))

    def _convert_h(self, h, hunit, tinc):
        if hunit == '%':
            return h
        elif hunit in ('C', 'F', 'K'):
            dewpointc = self._rh_to_dewpoint(h, tinc)
            return self._convert_t(dewpointc, hunit)
        else:
            raise NotImplementedError("Unrecognized humidity unit {}".format(hunit))

def _rh_to_dewpoint_magnus(rh, tc, b=18.678, c=257.14):
    """
    See https://en.wikipedia.org/wiki/Dew_point#Calculating_the_dew_point
    b = 18.678, c = 257.14 °C
    """
    from math import log as ln

    gam = ln(rh/100.) + b*tc / (c + tc)
    return c*gam / (b - gam)

def _rh_to_dewpoint_ardenbuck(rh, tc, b=18.678, c=257.14, d=234.5):
    """
    See https://en.wikipedia.org/wiki/Dew_point#Calculating_the_dew_point
    b = 18.678, c = 257.14 °C, d = 234.5 °C.
    """
    from math import exp, log as ln

    gam_m = ln((rh/100.)*exp((b - tc/d)*(tc/(c + tc))))
    return c*gam_m / (b - gam_m)

class BMESPIRegisterState(BME280BaseRegisterState, SPIRegisterState):
    def __init__(self, spi_bus, spi_device):
        kwargs = dict(spi_bus=spi_bus, spi_device=spi_device, register_size=8,
                      max_speed_hz=7800000, write_bit=7, write_set=False)
        super().__init__(**kwargs)

class BMEI2CRegisterState(BME280BaseRegisterState, I2CRegisterState):
    def __init__(self, **kwargs):
        kwargs.setdefault('device_address', 0x77)
        super().__init__(**kwargs)
