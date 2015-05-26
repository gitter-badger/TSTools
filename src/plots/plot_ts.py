# -*- coding: utf-8 -*-
# vim: set expandtab:ts=4
"""
/***************************************************************************
 Across year timeseries plot
                                 A QGIS plugin
 Plugin for visualization and analysis of remote sensing time series
                             -------------------
        begin                : 2013-03-15
        copyright            : (C) 2013 by Chris Holden
        email                : ceholden@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import datetime as dt

import numpy as np

from . import base_plot
from tstools.ts_driver.ts_manager import tsm
from tstools import settings


class TSPlot(base_plot.BasePlot):

    def __str__(self):
        return "Time Series Plot"

    def __init__(self, parent=None):
        ### Setup datasets
        # Actual data
        self.x = np.zeros(0)
        self.y = np.zeros(0)
        # Modeled fitted data
        self.mx = np.zeros(0)
        self.my = np.zeros(0)
        # Breaks
        self.bx = np.zeros(0)
        self.by = np.zeros(0)
        # Location of pixel plotted
        self.px = None
        self.py = None

        # Setup plots
        self.setup_plots()
        self.plot()

    def update_plot(self):
        """ Fetches new information and then calls to plot
        """

        print 'Updating plot...'

        self.px, self.py = tsm.ts.get_px(), tsm.ts.get_py()
        if self.px is not None and self.py is not None:
            # Add + 1 so we index on 1,1 instead of 0,0 (as in ENVI/MATLAB)
            self.px, self.py = self.px + 1, self.py + 1

        self.x = tsm.ts.dates
        self.y = tsm.ts.get_data(settings.plot['mask'])[settings.plot['band'], :]

        if settings.plot['fit'] is True and tsm.ts.result is not None:
            if len(tsm.ts.result) > 0:
                self.mx, self.my = tsm.ts.get_prediction(settings.plot['band'])
            else:
                self.mx, self.my = (np.zeros(0), np.zeros(0))
        if settings.plot['break'] is True and tsm.ts.result is not None:
            if len(tsm.ts.result) > 1:
                self.bx, self.by = tsm.ts.get_breaks(settings.plot['band'])
            else:
                self.bx, self.by = (np.zeros(0), np.zeros(0))
        self.plot()

    def plot(self):
        """ Matplotlib plot of time series
        """
        self.axes.clear()

        title = 'Time series - row: %s col: %s' % (
            str(self.py), str(self.px))
        self.axes.set_title(title)

        self.axes.set_xlabel('Date')
        if tsm.ts is None:
            self.axes.set_ylabel('Band')
        else:
            self.axes.set_ylabel(tsm.ts.band_names[settings.plot['band']])

        self.axes.grid(True)

        self.axes.set_ylim([settings.plot['min'][settings.plot['band']],
                            settings.plot['max'][settings.plot['band']]])

        if settings.plot['xmin'] is not None \
                and settings.plot['xmax'] is not None:
            self.axes.set_xlim([dt.date(settings.plot['xmin'], 01, 01),
                                dt.date(settings.plot['xmax'], 12, 31)])

        ### Plot time series data
        if settings.plot_symbol['enabled']:
            # Multiple plot calls to plot symbology
            for index, marker, color in zip(settings.plot_symbol['indices'],
                                            settings.plot_symbol['markers'],
                                            settings.plot_symbol['colors']):
                # Plot if we found anything
                if index.size > 0:
                    # Convert color from 0 - 255 to 0 - 1
                    color = [c / 255.0 for c in color]

                    self.axes.plot(self.x[index], self.y[index],
                                   marker=marker, ls='', color=color,
                                   picker=settings.plot['picker_tol'])
        else:
            # Plot just black dots if no symbology used
            line, = self.axes.plot(self.x, self.y,
                                   marker='o', ls='', color='k',
                                   picker=settings.plot['picker_tol'])

        # Plot modeled fit
        if settings.plot['fit'] is True:
            for i in xrange(len(self.mx)):
                self.axes.plot(self.mx[i], self.my[i], linewidth=2)

        # Plot break points
        if settings.plot['break'] is True:
            for i in xrange(len(self.bx)):
                self.axes.plot(self.bx[i], self.by[i], 'ro',
                               mec='r', mfc='none', ms=10, mew=5)

        # Redraw
        self.fig.tight_layout()
        self.fig.canvas.draw()

    def disconnect(self):
        pass
