# -*- coding: utf-8 -*-
# vim: set expandtab:ts=4
"""
/***************************************************************************
 TSTools metadata plotter symbology handler
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
from functools import partial
import logging

from PyQt4 import QtCore, QtGui

import matplotlib as mpl
import numpy as np

from ..ui_plot_symbology import Ui_Plot_Symbology

from .attach_md import AttachMetadata

from ..ts_driver.ts_manager import tsm
from .. import settings

logger = logging.getLogger('tstools')


class SymbologyControl(QtGui.QDialog, Ui_Plot_Symbology):
    """ Plot symbology controls """

    plot_symbology_applied = QtCore.pyqtSignal()

    def __init__(self, iface):
        # Qt setup
        self.iface = iface
        QtGui.QDialog.__init__(self)
        self.setupUi(self)

        keys = [k for k in mpl.lines.Line2D.markers.keys()
                if len(str(k)) == 1 and k != ' ']
        marker_texts = ['{k} - {v}'.format(k=k, v=mpl.lines.Line2D.markers[k])
                        for k in keys]
        self.markers = {k: text for k, text in zip(keys, marker_texts)}

    def setup_gui(self):
        """ Setup GUI with metadata from timeseries """
        self.setup_tables()

        # Add handler for stacked widget
        self.list_metadata.currentRowChanged.connect(self.metadata_changed)

        # Add slot for Okay / Apply
        self.button_box.button(QtGui.QDialogButtonBox.Apply).clicked.connect(
            self.symbology_applied)

        # Attach metadata
        self.attach_md = AttachMetadata(self.iface)
        self.attach_md.metadata_attached.connect(self.refresh_metadata)
        self.but_load_metadata.clicked.connect(self.load_metadata)

    def setup_tables(self):
        """ Setup tables """
        # Check for metadata
        md = getattr(tsm.ts, 'metadata', None)
        if not isinstance(md, list) or len(md) == 0:
            self.has_metadata = False
            self.setup_gui_nomd()
            return

        self.metadata = list(md)

        self.md = [getattr(tsm.ts, _md) for _md in md]

        self.has_metadata = True

        # Setup metadata listing
        self.md_str = getattr(tsm.ts, 'metadata_str', None)
        if not isinstance(self.md_str, list) or \
                len(self.md_str) != len(self.md):
            # If there is no description string, just use variable names
            self.md_str = list(md)

        # First item should be None to default to no symbology
        self.list_metadata.addItem(QtGui.QListWidgetItem('None'))
        for _md_str in self.md_str:
            self.list_metadata.addItem(QtGui.QListWidgetItem(_md_str))
        self.list_metadata.setCurrentRow(0)

        # Find all unique values for all metadata items
        self.unique_values = [None]
        for _md in self.md:
            self.unique_values.append(np.unique(_md))

        ### Init marker and color for unique values in all metadatas
        # list of dictionaries
        #   entries in list are for metadata types (entries in QListWidget)
        #       each list has dictionary for each unique value in metadata
        #           each list's dictionary has dict of 'color', 'marker'
        self.unique_symbologies = [None]
        for md in self.unique_values:
            if md is None:
                continue
            color = [0, 0, 0]
            marker = 'o'
            unique_md = {}
            for unique in md:
                unique_md[unique] = {'color': color,
                                     'marker': marker
                                     }
            self.unique_symbologies.append(unique_md)

        # Setup initial set of symbology for item selected
        self.tables = []
        logger.debug(self.unique_values)
        for i_md, unique_values in enumerate(self.unique_values):
            logger.debug('Init table {i}'.format(i=i_md))
            self.init_metadata(i_md)
        self.stack_widget.setCurrentIndex(0)

    def init_metadata(self, i_md):
        """ Initialize symbology table with selected metadata attributes """
        if not self.has_metadata:
            return

        # Add QTableWidget
        table = QtGui.QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['Value', 'Marker', 'Color'])
        table.horizontalHeader().setStretchLastSection(True)

        if self.unique_values[i_md] is None:
            table.setRowCount(0)
        else:
            # Populate table
            table.setRowCount(len(self.unique_values[i_md]))

            for i, unique in enumerate(self.unique_values[i_md]):
                # Fetch current values
                color = self.unique_symbologies[i_md][unique]['color']
                marker = self.unique_symbologies[i_md][unique]['marker']

                # Label for value
                lab = QtGui.QLabel(str(unique))
                lab.setAlignment(QtCore.Qt.AlignCenter)

                # Possible markers in combobox
                cbox = QtGui.QComboBox()
                for m in self.markers.values():
                    cbox.addItem(m)
                cbox.setCurrentIndex(cbox.findText(self.markers[marker]))
                cbox.currentIndexChanged.connect(partial(self.marker_changed,
                                                 i, i_md, unique))

                # Colors
                button = QtGui.QPushButton('Color')
                button.setAutoFillBackground(True)
                self.set_button_color(button, color)

                button.pressed.connect(partial(self.color_button_pressed,
                                               i, i_md, unique))

                # Add to table
                table.setCellWidget(i, 0, lab)
                table.setCellWidget(i, 1, cbox)
                table.setCellWidget(i, 2, button)

        self.tables.append(table)
        self.stack_widget.insertWidget(i_md, table)

    @QtCore.pyqtSlot()
    def color_button_pressed(self, i, i_md, unique):
        """ Slot for color chooser

        Pops up color chooser dialog and stores values
        """
        # Current color
        c = self.unique_symbologies[i_md][unique]['color']
        current_c = QtGui.QColor(c[0], c[1], c[2])

        # Get new color
        color_dialog = QtGui.QColorDialog()

        new_c = color_dialog.getColor(current_c, self,
                                      'Pick color for {u}'.format(u=unique))
        if not new_c.isValid():
            return

        # Update color and button
        self.unique_symbologies[i_md][unique]['color'] = [new_c.red(),
                                                          new_c.green(),
                                                          new_c.blue()
                                                          ]
        button = self.tables[i_md].cellWidget(i, 2)

        self.set_button_color(button,
                              self.unique_symbologies[i_md][unique]['color'])

    @QtCore.pyqtSlot(int)
    def marker_changed(self, i, i_md, unique, index):
        """ Slot for changing marker style """
        # Find combobox
        cbox = self.tables[i_md].cellWidget(i, 1)
        # Update value
        self.unique_symbologies[i_md][unique]['marker'] = \
            self.markers.keys()[index]

    @QtCore.pyqtSlot(int)
    def metadata_changed(self, row):
        """ Switch metadata tables """
        self.stack_widget.setCurrentIndex(row)

    def set_button_color(self, button, c):
        """ Sets button text color """
        c_str = 'rgb({r}, {g}, {b})'.format(r=c[0], g=c[1], b=c[2])
        style = 'QPushButton {{color: {c}; font-weight: bold}}'.format(c=c_str)

        button.setStyleSheet(style)

    @QtCore.pyqtSlot()
    def symbology_applied(self):
        """ Slot for Apply or OK button on QDialogButtonBox

        Emits "plot_symbology_applied" to Controls, which pushes to Controller,
        and then to the plots
        """
        # Send symbology to settings
        row = self.list_metadata.currentRow()

        if row == 0:
            # If row == 0, either no symbology or no metadata
            settings.plot_symbol['enabled'] = False
            settings.plot_symbol['indices'] = None
            settings.plot_symbol['markers'] = None
            settings.plot_symbol['colors'] = None
        else:
            settings.plot_symbol['enabled'] = True
            self.parse_metadata_symbology()

        # Emit changes
        self.plot_symbology_applied.emit()

    @QtCore.pyqtSlot()
    def load_metadata(self):
        """ Open AttachMetadata window to retrieve more metadata """
        self.attach_md.show()

    @QtCore.pyqtSlot()
    def refresh_metadata(self):
        """ Reset old table and load up new metadata """
        self.update_tables()

    def update_tables(self):
        """ Setup tables """
        # Check for new metadata
        new_i = []
        for i, (_md, _md_str) in enumerate(zip(tsm.ts.metadata,
                                               tsm.ts.metadata_str)):
            if _md not in self.metadata:
                self.metadata.append(_md)
                self.md.append(getattr(tsm.ts, _md))
                self.md_str.append(_md_str)
                new_i.append(i)

        # First item should be None to default to no symbology
        for i, _md_str in enumerate(self.md_str):
            if i in new_i:
                self.list_metadata.addItem(QtGui.QListWidgetItem(_md_str))
        self.list_metadata.setCurrentRow(0)

        # Find all unique values for all metadata items
        self.unique_values = [None]
        for _md in self.md:
            self.unique_values.append(np.unique(_md))

        ### Init marker and color for unique values in all metadatas
        # list of dictionaries
        #   entries in list are for metadata types (entries in QListWidget)
        #       each list has dictionary for each unique value in metadata
        #           each list's dictionary has dict of 'color', 'marker'
        self.unique_symbologies = [None]
        for md in self.unique_values:
            if md is None:
                continue
            color = [0, 0, 0]
            marker = 'o'
            unique_md = {}
            for unique in md:
                unique_md[unique] = {'color': color,
                                     'marker': marker
                                     }
            self.unique_symbologies.append(unique_md)

        # Setup initial set of symbology for item selected
        for i_md, unique_values in enumerate(self.unique_values):
            if (i_md - 1) not in new_i:
                continue
            print 'Init table {i}'.format(i=i_md)
            self.init_metadata(i_md)

        self.stack_widget.setCurrentIndex(0)

    def parse_metadata_symbology(self):
        """ Parses TS's metadata to update the symbology attributes """
        logger.debug(
            'Updating symbology?: %s' % str(settings.plot_symbol['enabled']))

        if settings.plot_symbol['enabled']:
            # Determine current metadata
            row = self.list_metadata.currentRow()

            # Update metadata
            self.md[row - 1] = getattr(tsm.ts, tsm.ts.metadata[row - 1])

            # Grab unique values
            keys = self.unique_symbologies[row].keys()
            # Grab unique value's markers and colors
            indices = []
            markers = []
            colors = []
            for k in keys:
                indices.append(np.where(self.md[row - 1] == k)[0])
                markers.append(self.unique_symbologies[row][k]['marker'])
                colors.append(self.unique_symbologies[row][k]['color'])
                print (self.md[row - 1] == k).sum()
            settings.plot_symbol['indices'] = list(indices)
            settings.plot_symbol['markers'] = list(markers)
            settings.plot_symbol['colors'] = list(colors)

#    def reset_tables(self):
#        """ Removes all metadata items from table """
#        # Remove all table entries and stacked widgets
#        self.tables = []
#        self.list_metadata.clear()
#
#        print self.stack_widget.count()
#        for i in range(self.stack_widget.count()):
#            print 'Removing stacked widget {i}'.format(i=i)
#            w = self.stack_widget.widget(i)
#            print w
#            if w:
#                self.stack_widget.removeWidget(w)
#                w.deleteLater()
#
#        self.stack_widget.update()
#
#        self.widget_sym.layout().removeWidget(self.stack_widget)
#        self.stack_widget = QtGui.QStackedWidget(self.widget_sym)
#
#        print self.stack_widget.count()

    def setup_gui_nomd(self):
        """ Setup GUI if timeseries has no metadata """
        item = QtGui.QListWidgetItem('No Metadata')
        self.list_metadata.addItem(item)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
