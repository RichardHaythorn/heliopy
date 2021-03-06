"""
Methods for importing data from the Cassini spacecraft.
"""
import datetime
import os
import pathlib
import h5py
import pandas as pd
import calendar
import astropy.units as u
import pvl
import numpy as np
import datetime as dt
from struct import unpack, calcsize
import sunpy

from collections import OrderedDict
from heliopy.data import util
from heliopy import config

data_dir = pathlib.Path(config['download_dir'])
use_hdf = config['use_hdf']
cassini_dir = data_dir / 'cassini'

# These mappings from months to strings are used in directory names
month2str = {1: '001_031_JAN',
             2: '032_059_FEB',
             3: '060_090_MAR',
             4: '091_120_APR',
             5: '121_151_MAY',
             6: '152_181_JUN',
             7: '182_212_JUL',
             8: '213_243_AUG',
             9: '244_273_SEP',
             10: '274_304_OCT',
             11: '305_334_NOV',
             12: '335_365_DEC'}
leapmonth2str = {1: '001_031_JAN',
                 2: '032_060_FEB',
                 3: '061_091_MAR',
                 4: '092_121_APR',
                 5: '122_152_MAY',
                 6: '153_182_JUN',
                 7: '183_213_JUL',
                 8: '214_244_AUG',
                 9: '245_274_SEP',
                 10: '275_305_OCT',
                 11: '306_335_NOV',
                 12: '336_366_DEC'}


class _mag1minDownloader(util.Downloader):
    def __init__(self, coords):
        valid_coords = ['KRTP', 'KSM', 'KSO', 'RTN']
        if coords not in valid_coords:
            raise ValueError('coords must be one of {}'.format(valid_coords))
        self.coords = coords

        Rs = u.def_unit('saturnRad', 60268 * u.km)
        if (coords == 'KRTP'):
            self.units = OrderedDict([('Bx', u.nT), ('By', u.nT), ('Bz', u.nT),
                                      ('X', Rs), ('|B|', u.nT),
                                      ('Y', u.deg),
                                      ('Z', u.deg),
                                      ('Local hour', u.dimensionless_unscaled),
                                      ('n points', u.dimensionless_unscaled)])
        if (coords == 'RTN'):
            self.units = OrderedDict([('Bx', u.nT), ('By', u.nT), ('Bz', u.nT),
                                      ('X', u.AU), ('Y', u.AU), ('Z', u.AU),
                                      ('|B|', u.nT),
                                      ('Local hour', u.dimensionless_unscaled),
                                      ('n points', u.dimensionless_unscaled)])
        if (coords == 'KSM' or coords == 'KSO'):
            self.units = OrderedDict([('Bx', u.nT), ('By', u.nT), ('Bz', u.nT),
                                      ('X', Rs), ('Y', Rs), ('Z', Rs),
                                      ('|B|', u.nT),
                                      ('Local hour', u.dimensionless_unscaled),
                                      ('n points', u.dimensionless_unscaled)])

    def intervals(self, starttime, endtime):
        return self.intervals_yearly(starttime, endtime)

    def fname(self, interval):
        year = interval.start.strftime('%Y')
        return f'{year}_FGM_{self.coords}_1M.TAB'

    def local_dir(self, interval):
        return pathlib.Path('cassini') / 'mag' / '1min'

    def download(self, interval):
        local_dir = self.local_path(interval).parent
        local_dir.mkdir(parents=True, exist_ok=True)
        year = interval.start.strftime('%Y')
        base_url = ('https://pds-ppi.igpp.ucla.edu/ditdos/download?'
                    'id=pds://PPI/CO-E_SW_J_S-MAG-4-SUMM-1MINAVG-V2.0/DATA')
        url = '{}/{}'.format(base_url, year)
        util._download_remote(url,
                              self.fname(interval),
                              local_dir)

    def load_local_file(self, interval):
        f = open(self.local_path(interval))
        if 'error_message' in f.readline():
            f.close()
            os.remove(f.name)
            raise util.NoDataError()
        data = pd.read_csv(f,
                           names=['Time', 'Bx', 'By', 'Bz', '|B|',
                                  'X', 'Y', 'Z', 'Local hour', 'n points'],
                           delim_whitespace=True,
                           parse_dates=[0], index_col=0)
        f.close()
        return data


def mag_1min(starttime, endtime, coords):
    """
    Import 1 minute magnetic field from Cassini.

    See http://pds-ppi.igpp.ucla.edu/search/view/?f=yes&id=pds://PPI/CO-E_SW_J_S-MAG-4-SUMM-1MINAVG-V1.0
    for more information.

    Cassini Orbiter Magnetometer Calibrated MAG data in 1 minute averages
    available covering the period 1999-08-16 (DOY 228) to 2016-12-31 (DOY 366).
    The data are provided in RTN coordinates throughout the mission, with
    Earth, Jupiter, and Saturn centered coordinates for the respective
    flybys of those planets.

    Parameters
    ----------
    starttime : datetime
        Interval start time.
    endtime : datetime
        Interval end time.
    coords : strings
        Requested coordinate system. Must be one of
        ``['KRTP', 'KSM', 'KSO', 'RTN']``

    Returns
    -------
    data : :class:`~sunpy.timeseries.TimeSeries`
        Requested data
    """
    dl = _mag1minDownloader(coords)
    return dl.load(starttime, endtime)


def mag_hires(starttime, endtime, try_download=True):
    """
    Import high resolution magnetic field from Cassini.

    See http://pds-ppi.igpp.ucla.edu/search/view/?f=yes&id=pds://PPI/CO-E_SW_J_S-MAG-3-RDR-FULL-RES-V1.0
    for more information.

    Cassini Orbiter Magnetometer Calibrated MAG data at the highest time
    resolution available covering the period 1999-08-16 (DOY 228) to
    2016-12-31 (DOY 366).

    The data are in RTN coordinates prior Cassini's arrival at Saturn, and
    Kronographic (KRTP) coordinates at Saturn (beginning 2004-05-14, DOY 135).

    Parameters
    ----------
    starttime : datetime
        Interval start time.
    endtime : datetime
        Interval end time.

    Returns
    -------
    data : :class:`~sunpy.timeseries.TimeSeries`
        Requested data
    """
    remote_base_url = ('https://pds-ppi.igpp.ucla.edu/ditdos/download?id='
                       'pds://PPI/CO-E_SW_J_S-MAG-3-RDR-FULL-RES-V2.0/DATA')
    dirs = []
    fnames = []
    extension = '.TAB'
    units = OrderedDict([('Bx', u.nT), ('By', u.nT), ('Bz', u.nT),
                         ('coords', u.dimensionless_unscaled)])
    local_base_dir = cassini_dir / 'mag' / 'hires'

    for [day, _, _] in util._daysplitinterval(starttime, endtime):
        year = day.year
        if calendar.isleap(year):
            monthstr = leapmonth2str[day.month]
        else:
            monthstr = month2str[day.month]

        if day < datetime.date(2004, 5, 14):
            coords = 'RTN'
        else:
            coords = 'KRTP'
        doy = day.strftime('%j')
        dirs.append(pathlib.Path(str(year)) / monthstr)
        fnames.append(str(year)[2:] + doy + '_FGM_{}'.format(coords))

    def download_func(remote_base_url, local_base_dir,
                      directory, fname, remote_fname, extension):
        url = remote_base_url + '/' + str(directory)
        util._download_remote(url, fname + extension,
                              local_base_dir / directory)

    def processing_func(f):
        if 'error_message' in f.readline():
            f.close()
            os.remove(f.name)
            raise util.NoDataError()
        df = pd.read_csv(f, names=['Time', 'Bx', 'By', 'Bz'],
                         delim_whitespace=True,
                         parse_dates=[0], index_col=0)
        return df

    return util.process(dirs, fnames, extension, local_base_dir,
                        remote_base_url, download_func, processing_func,
                        starttime, endtime, units=units,
                        try_download=try_download)


class _capsDownloader(util.Downloader):
    base_url = ('https://pds-ppi.igpp.ucla.edu/ditdos/download?id='
                'pds://PPI/CO-E_J_S_SW-CAPS-3-CALIBRATED-V1.0/DATA/CALIBRATED')

    def intervals(self, starttime, endtime):
        return self.intervals_sixhourly(starttime, endtime)

    def fname(self, interval):
        year = interval.start.strftime('%Y')
        doy = interval.start.strftime('%j')
        hour = interval.start.strftime('%H')
        return f'{self.sensor.upper()}_{year}{doy}{hour}_V01'

    def local_dir(self, interval):
        year = interval.start.strftime('%Y')
        doy = interval.start.strftime('%j')
        return (pathlib.Path('cassini') / 'caps' / self.sensor /
                year / doy)

    def intervals_sixhourly(self, starttime, endtime):
        startdatetime = dt.datetime.combine(starttime.date(), dt.time(starttime.hour - (starttime.hour % 6)))
        enddatetime = dt.datetime.combine(endtime.date(), dt.time(endtime.hour - (endtime.hour % 6)))
        intervallist = sunpy.time.TimeRange(startdatetime, enddatetime).window(6 * u.hour, window=6 * u.hour)
        return intervallist

    def download(self, interval):
        local_dir = self.local_path(interval).parent
        local_dir.mkdir(parents=True, exist_ok=True)
        year = interval.start.strftime('%Y')
        doy = interval.start.strftime('%j')
        url = '{}/{}/{}'.format(self.base_url, year, doy)
        util._download_remote(url, self.fname(interval) + '.DAT', local_dir)
        util._download_remote(url, self.fname(interval) + '.LBL', local_dir)
        util._download_remote(url, self.sensor.upper() + "_V01.FMT", local_dir)
        create_caps_hdf5_file(local_dir / (self.fname(interval) + '.DAT'),
                              local_dir / (self.fname(interval) + '.LBL'),
                              local_dir / (self.sensor.upper() + "_V01.FMT"))

    def load_local_file(self, interval):
        hdf_path = data_dir / self.local_dir(interval) / (self.fname(interval) + '.hdf')
        return self.load_local_caps_hdf_file(hdf_path)

    def load_local_hdf_file(self, hdf_path):
        return self.load_local_caps_hdf_file(hdf_path)


class _elsDownloader(_capsDownloader):
    units = OrderedDict([])
    for i in range(63):
        units[i] = u.ct / u.s

    def __init__(self, sensor, anode):
        self.sensor = sensor
        self.anode = anode

    def load_local_caps_hdf_file(self, hdf_path):
        hdf5file = h5py.File(hdf_path, 'r')
        df = pd.DataFrame(np.flip(np.array(hdf5file['DATA'][:, :, self.anode, 0]), axis=1))
        df['Time'] = [datetime.datetime.strptime(item.decode("ASCII"), "%Y-%jT%H:%M:%S.%f") for item in hdf5file['UTC']]
        hdf5file.close()
        return df


def caps_els(starttime, endtime, anode):
    """
       Import calibrated electron data from Cassini CAPS ELS.

       See https://pds-ppi.igpp.ucla.edu/search/view/?id=pds://PPI/CO-E_J_S_SW-CAPS-3-CALIBRATED-V1.0
       for more information.

       Cassini Orbiter Cassini Plasma Spectrometer (CAPS) Electron Spectrometer (ELS)
       calibrated data covering the solar wind over the intervals 1999-004 (4 Jan) to
       1999-021 (21 Jan), 1999-232 (20 Aug) to 1999-257 (14 Sep), 2000-190 (8 Jul) to 2000-309 (4 Nov),
       and 2001-120 (30 Apr)to 2004-135 (14 May), at Earth from 1999-229 (17 Aug) to 1999-231 (19 Aug),
       at Jupiter from 2000-310 (4 Nov) to 2001-119 (29 Apr), and at Saturn over the interval 2004-136 (15 May)
       to 2012-154 (02 Jun).

       Parameters
       ----------
       starttime : datetime
           Interval start time.
       endtime : datetime
           Interval end time.
       anode : int
           Requested CAPS ELS. Must be in 0-7 range

       Returns
       -------
       data : :class:`~sunpy.timeseries.TimeSeries`
           Requested data
       """
    dl = _elsDownloader("els", anode)
    return dl.load(starttime, endtime)


def create_caps_hdf5_file(datafilepath, labelfilepath, formatfilepath):
    """
    Creates a hdf5 file given a .DAT, .LBL and .FMT file
    """

    # This bit finds where the format of the data is stored
    dataformatlocation = pvl.load(formatfilepath.__str__())
    labelinputfile = open(formatfilepath.__str__(), 'r')

    # This creates a dictionary containing the structure of the data, based on RJW comments in files
    datastructure = {}
    for row in labelinputfile:
        if row[:6] == "/* RJW":
            templist = row.rstrip()[7:-2].split(",")
            newdataitem = [x.lstrip().rstrip() for x in templist]
            datastructure[newdataitem[0]] = newdataitem[1:]

    # Fix Cassini CAPS shapes
    if "ELS" in pvl.load(labelfilepath.__str__())['STANDARD_DATA_PRODUCT_ID']:
        datastructure["DATA"] = ['f', '3', '63', '8', '1']
        datastructure["J2000_TO_RTP"] = ['f', '2', '3', '3']
        datastructure["SC_TO_J2000"] = ['f', '2', '3', '3']
    if "IBS" in pvl.load(labelfilepath.__str__())['STANDARD_DATA_PRODUCT_ID']:
        datastructure["DATA"] = ['f', '3', '255', '3', '1']
        datastructure["J2000_TO_RTP"] = ['f', '2', '3', '3']
        datastructure["SC_TO_J2000"] = ['f', '2', '3', '3']

    recordbytes = pvl.load(labelfilepath.__str__())['RECORD_BYTES']
    numberofrows = pvl.load(labelfilepath.__str__())['TABLE']['ROWS']
    datainputfile = open(datafilepath.__str__(), 'rb')

    # Opens a HDF5 file and writes attributes contain in
    f = h5py.File(datafilepath.with_suffix(".hdf"), 'w')
    for item in pvl.load(labelfilepath.__str__()).items():
        if item[0] in ['TABLE', 'COLUMN', 'CONTAINER']:
            continue
        if isinstance(item[1], int):
            f.attrs[item[0]] = item[1]
        else:
            f.attrs[item[0]] = str(item[1])

    for itemcounter, item in enumerate(dataformatlocation.items()):
        if isinstance(item[1], pvl.PVLObject):
            if item[0] == "CONTAINER":
                tempname = item[1]['NAME'].rsplit("_", 1)[0]
            else:
                tempname = item[1]['NAME']
            dataitem = datastructure[tempname]
            dataformat = dataitem[0]
            datadim = int(dataitem[1])
            datashape = []
            for i in range(datadim):
                datashape.append(int(dataitem[2 + i]))

            numofnum = np.prod(datashape)
            datainputfile.seek(item[1]['START_BYTE'] - 1, 0)
            tempshape = [numberofrows] + datashape

            # Characters/Strings annoying to deal with, use separate bit
            if dataformat == "c":
                temp = []
                for i in range(numberofrows):
                    numofbytes = calcsize(numofnum * dataformat)
                    entry = datainputfile.read(numofbytes)
                    temp.append(unpack("<" + (str(numofnum) + "s"), entry)[0])
                    datainputfile.seek(recordbytes - numofbytes, 1)
                f.create_dataset(tempname, data=temp)
            else:
                temparray = np.zeros(tempshape)
                for i in range(numberofrows):
                    numofbytes = calcsize(numofnum * dataformat)
                    entry = datainputfile.read(numofbytes)
                    temp = unpack("<" + (numofnum * dataformat), entry)
                    temparray[i] = np.array(temp).reshape(datashape)
                    # print(temp,len(temp))
                    datainputfile.seek(recordbytes - numofbytes, 1)
                f.create_dataset(tempname, data=temparray)
    f.close()
