import abc

import numpy as np

from . import utils


class AbstractTimeSeriesDriver(object):
    """ Abstract base class representing a remote sensing time series.

    AbstractTimeSeriesDriver class is meant to be sub-classed and its methods
    overriden. This interface simply defines attributes and methods expected
    by "TSTools" QGIS plugin.

    Required attributes:
      description (str): description of timeseries type
      location (str): root location of timeseries on disk
      ts (list): a list of `Series` class for each timeseries in driver
      mask_values (iterable, or None): sequence of mask values, if any
      pixel_pos (str): location of pixel for display
      has_results (bool): True/False if model supports timeseries model
        fitting and visualization

    Extra Attributes:
      config (iterable): list of variables used for timeseries configuration
      config_names (iterable): list names of variables used for timeseries
        configuration

      controls (iterable): list of variables used for custom controls within
        "Controls" tab
      controls_names (iterable): list of names of variables used for custom
        controls within "Controls" tab

    Required Methods:
      fetch_data: read data for a given X/Y, yielding progress as percentage
      fetch_results: read in or calculate timeseries fetch_results
      get_data: return data for a specified band
      get_prediction: return prediction for a specified band
      get_breaks: return timeseries break points for a specified band

    """

    __metaclass__ = abc.ABCMeta

    # No extra configuration by default
    config = []
    config_names = []

    # No extra controls by default
    controls = []
    controls_names = []

    def __init__(self, location, config=None):
        self.location = location
        if config:
            utils.set_custom_config(self, config)

    def __repr__(self):
        return "A {d} ({c}) timeseries of {n} images at {m}".format(
            d=self.description,
            c=self.__class__.__name__,
            n=len(self.images),
            m=hex(id(self)))

    @abc.abstractproperty
    def description(self):
        pass

    @abc.abstractproperty
    def location(self):
        pass

    @abc.abstractproperty
    def ts(self):
        pass

    @abc.abstractproperty
    def mask_values(self):
        pass

    @abc.abstractproperty
    def pixel_pos(self):
        pass

    @abc.abstractproperty
    def has_results(self):
        pass

    @abc.abstractmethod
    def fetch_data(self, x, y, crs_wkt):
        """ Read data for a given x, y coordinate in a given CRS

        Args:
          mx (float): map X location
          my (float): map Y location
          crs_wkt (str): Well Known Text (Wkt) Coordinate reference system
            string describing (x, y)

        Yields:
          float: current retrieval progress (0 to 1)

        """
        pass

    @abc.abstractmethod
    def fetch_results(self):
        """ Read or calculate results for current pixel """
        pass

    @abc.abstractmethod
    def get_data(self, band, mask=True):
        """ Return data for a given band

        Args:
          band (int): index of band to return
          mask (bool, optional): return data masked or left unmasked, if
            supported by driver implementation

        Returns:
          np.ndarray: 1D NumPy array containing data

        """
        pass

    @abc.abstractmethod
    def get_prediction(self, band):
        """ Return prediction for a given band

        Args:
          band (int): index of band to return

        Returns:
          iterable: sequence of tuples (1D NumPy arrays, x and y) containing
            predictions

        """
        pass

    @abc.abstractmethod
    def get_breaks(self, band):
        """ Return break points for a given band

        Args:
          band (int): index of band to return

        Returns:
          iterable: sequence of tuples (1D NumPy arrays, x and y) containing
            break points

        """
        pass


class Series(object):
    """ A container class for timeseries driven by a TimeSeries driver

    Note:
      You can set class attributes using an optionally supplied configuration
        dictionary when instantiating the class.

    Attributes:
      images (np.ndarray): NumPy structured array containing attributes for all
        timeseries images. Structured array columns must include
        "filename" (str), "path" (str), "id" (str), "date" (dt.Date), and
        "ordinal" (int).
      band_names (iterable): list of names describing each band

      symbology_hint_indices (tuple): three band indices (RGB) used for default
        symbology
      symbology_hint_minmax (iterable): one or more pairs of integers used as
        the minimum and maximum scaling for default image symbology

      metadata (iterable): list of variables used for plot and image table
        metadata
      metadata_table (iterable): list of True/False for each metadata variable
        indicating suitability of variable within images table on "Controls" tab
      metadata_names (iterable): list of names of variables used for plot and
        image table metadata

    """
    images = np.empty(0,
                      dtype=[('filename', object),
                             ('path', object),
                             ('id', object),
                             ('date', object),
                             ('ordinal', 'u4')])
    band_names = []

    # Basic symbology hints by default
    symbology_hint_indices = [3, 2, 1]
    # Specify two numbers (int or float) for one min/max for all bands
    # OR specify np.ndarray for each band in dataset for min and max
    #     e.g. symbology_hint_minmax = [np.zeros(8), np.ones(8) * 10000]
    symbology_hint_minmax = [0, 1]

    metadata = []
    metadata_table = []
    metadata_names = []

    def __init__(self, config=None):
        if config:
            self.__dict__.update(config)
