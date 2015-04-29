# -*- coding: utf-8 -*
# vim: set expandtab:ts=4
"""
/***************************************************************************
 TSTools controller for timeseries driver interactions
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
import itertools
import logging

from PyQt4 import QtCore
from PyQt4 import QtGui
from qgis.core import *
from qgis.gui import QgsMessageBar

import matplotlib as mpl
import numpy as np

# from timeseries_ccdc import CCDCTimeSeries
from .ts_driver.ts_manager import tsm
from . import settings as setting

logger = logging.getLogger('tstools')


class DataRetriever(QtCore.QObject):

    retrieve_update = QtCore.pyqtSignal(int)
    retrieve_complete = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.running = False
        self.read_from_cache = False
        self.can_writecache = False
        self.index = 0

    def _retrieve_ts_pixel(self):
        """ If we can't just get from cache, grab from images """
        t = QtCore.QTime()
        t.start()

        while (t.elapsed() < 150):
            # Are we done?
            if self.index == tsm.ts.length:
                self.running = False
                self._got_ts_pixel()
                return

            # If not, get pixel and index++
            tsm.ts.retrieve_pixel(self.index)
            self.index += 1
            QtGui.QApplication.instance().processEvents()

        self.retrieve_update.emit(self.index + 1)

        # Use QTimer to call this method again
        if self.running:
            QtCore.QTimer.singleShot(0, self._retrieve_ts_pixel)

    def _got_ts_pixel(self):
        """ Finish off rest of process when getting pixel data """
        tsm.ts.apply_mask()

        if tsm.ts.write_cache and not self.read_from_cache:
            try:
                self.can_writecache = tsm.ts.write_to_cache()
            except:
                logger.error('Could not write to cache file')
            else:
                if self.can_writecache:
                    logger.debug('Wrote to cache file')

        if tsm.ts.has_results:
            tsm.ts.retrieve_result()

        self.retrieve_complete.emit()

    def get_ts_pixel(self):
        """ Retrieves time series, emitting status updates """
        # First check if time series has a readable cache
        if tsm.ts.read_cache and tsm.ts.cache_folder is not None:
            self.read_from_cache = tsm.ts.retrieve_from_cache()

        if self.read_from_cache:
            # We've read from cache - finish process
            self._got_ts_pixel()
        if not self.read_from_cache:
            # We can't read from or there is no cache - retrieve from images
            self.index = 0
            self.running = True
            QtCore.QTimer.singleShot(0, self._retrieve_ts_pixel)


class Controller(QtCore.QObject):

    enable_tool = QtCore.pyqtSignal()
    disable_tool = QtCore.pyqtSignal()

    def __init__(self, iface, control, ts_plot, doy_plot, parent=None):
        """
        Controller stores options specified in control panel & makes them
        available for plotter by handling all signals...
        """
        super(Controller, self).__init__()

        self.iface = iface
        self.ctrl = control
        self.ts_plot = ts_plot
        self.doy_plot = doy_plot

        # Which tab do we have open?
        self.active_plot = self.ts_plot

        # Are we configured with a time series?
        self.configured = False

        # Setup threading for data retrieval
#        self.retrieve_thread = QtCore.QThread()
        self.retriever = DataRetriever()
#        self.retriever.moveToThread(self.retrieve_thread)

# Setup
    def _init_symbology(self):
        """
        Initializes the layer symbology using defaults or specified hints
        """
        # Default band min/max
        setting.symbol['min'], setting.p_symbol['min'] = \
            (np.zeros(tsm.ts.n_band, dtype=np.int), ) * 2
        setting.symbol['max'], setting.p_symbol['max'] = \
            (np.ones(tsm.ts.n_band, dtype=np.int) * 10000, ) * 2

        # Apply symbology hints if exists
        if hasattr(tsm.ts, 'symbology_hint_indices'):
            i = tsm.ts.symbology_hint_indices
            if isinstance(i, (tuple, list)) and len(i) == 3:
                logger.debug('Applying RGB index symbology hint')
                setting.p_symbol['band_red'], \
                    setting.p_symbol['band_green'], \
                    setting.p_symbol['band_blue'] = i[0], i[1], i[2]
                setting.symbol['band_red'], \
                    setting.symbol['band_green'], \
                    setting.symbol['band_blue'] = i[0], i[1], i[2]
            else:
                logger.warning(
                    'RGB index symbology hint improperly described')

        # Make sure band used in symbology exists
        if setting.symbol['band_red'] > tsm.ts.n_band:
            logger.warning('Fixing red band to largest band in dataset')
            setting.symbol['band_red'] = tsm.ts.n_band - 1
            setting.p_symbol['band_red'] = tsm.ts.n_band - 1

        if setting.symbol['band_green'] > tsm.ts.n_band:
            logger.warning('Fixing green band to largest band in dataset')
            setting.symbol['band_green'] = tsm.ts.n_band - 1
            setting.p_symbol['band_green'] = tsm.ts.n_band - 1

        if setting.symbol['band_blue'] > tsm.ts.n_band:
            logger.warning('Fixing blue band to largest band in dataset')
            setting.symbol['band_blue'] = tsm.ts.n_band - 1
            setting.p_symbol['band_blue'] = tsm.ts.n_band - 1

        if hasattr(tsm.ts, 'symbology_hint_minmax'):
            i = tsm.ts.symbology_hint_minmax
            if isinstance(i, (tuple, list)) and len(i) == 2:
                logger.debug('Applying RGB min/max symbology hint')
                # One min/max for all bands
                if isinstance(i[1], (int, float)) and \
                        isinstance(i[0], (int, float)):
                    setting.symbol['min'], setting.p_symbol['min'] = \
                        (np.ones(tsm.ts.n_band) * i[0], ) * 2
                    setting.symbol['max'], setting.p_symbol['max'] = \
                        (np.ones(tsm.ts.n_band) * i[1], ) * 2
                # Specified min/max for all bands
                elif isinstance(i[0], np.ndarray) and \
                        isinstance(i[1], np.ndarray):
                    setting.symbol['min'] = i[0]
                    setting.symbol['max'] = i[1]
                else:
                    logger.warning('Could not use symbology min/max hint')
            else:
                logger.warning(
                    'RGB min/max symbology hint improperly described')

    def get_time_series(self, TimeSeries,
                        location, custom_options=None):
        """
        Loads the time series class when called by ccdctools and feeds
        information to controls & plotter
        """
        try:
            tsm.ts = TimeSeries(location, custom_options)
        except:
            raise

        if tsm.ts:
            # Setup raster display symbology
            self._init_symbology()

            # Control panel
            self.ctrl.init_options()
            self.ctrl.init_custom_options()
            self.ctrl.init_plot_options()
            self.ctrl.init_symbology()
            self.ctrl.update_table()

            # Wire signals for GUI
            self.disconnect()
            self.add_signals()

            self.retriever.retrieve_update.connect(
                self.retrieval_progress_update)
            self.retriever.retrieve_complete.connect(
                self.retrieval_progress_complete)
#            self.retrieve_thread.start()

            self.configured = True
            return True

### Communications
    def update_display(self):
        """
        Once ts is read, update controls & plot with relevant information
        (i.e. update)
        """
        # Update metadata
        self.ctrl.symbology_controls.parse_metadata_symbology()
        if setting.plot['auto_scale']:
            self.calculate_scale()
        self.ctrl.update_plot_options()
        self.ts_plot.update_plot()
        self.doy_plot.update_plot()

    def update_masks(self):
        """ Signal to TS to update the mask and reapply """
        logger.debug('Updated masks - refreshing plots')
        tsm.ts.mask_val = setting.plot['mask_val']
        tsm.ts.apply_mask(mask_val=setting.plot['mask_val'])
        self.update_display()

### Common layer manipulation
    def add_map_layer(self, index):
        """
        Method called when adding an image via the table or plot.
        """
        logger.debug('Adding map layer')
        reg = QgsMapLayerRegistry.instance()

        if type(index) == np.ndarray:
            if len(index) > 1:
                logger.warning('More than one index clicked - taking first')
                index = index[0]

        # Which layer are we adding?
        added = [(tsm.ts.filepaths[index] == layer.source(), layer)
                 for layer in reg.mapLayers().values()]
        # Check if we haven't already added it
        if all(not add[0] for add in added) or len(added) == 0:
            # Create
            rlayer = QgsRasterLayer(tsm.ts.filepaths[index],
                                    tsm.ts.image_names[index])
            if rlayer.isValid():
                reg.addMapLayer(rlayer)

            # Add to settings "registry"
            setting.image_layers.append(rlayer)
            # Handle symbology
            self.apply_symbology(rlayer)

# If we have already added it, move it to top
#        elif any(add[0] for add in added):
#            index = [i for i, tup in enumerate(added) if tup[0] == True][0]
#            self.move_layer_top(added[index][1].id())

    def map_layers_added(self, layers):
        """
        Check if newly added layer is part of filepaths; if so, make sure image
        checkbox is clicked in the images tab. Also ensure
        setting.canvas['click_layer_id'] gets moved to the top
        """
        logger.debug('Added a map layer')
        for layer in layers:
            rows_added = [row for (row, imgfile) in enumerate(tsm.ts.filepaths)
                          if layer.source() == imgfile]
            logger.debug('Added these rows: %s' % str(rows_added))
            for row in rows_added:
                item = self.ctrl.image_table.item(row, 0)
                if item:
                    if item.checkState() == QtCore.Qt.Unchecked:
                        item.setCheckState(QtCore.Qt.Checked)

#        # Move pixel highlight back to top
#        if setting.canvas['click_layer_id']:
#            logger.debug('Moving click layer back to top')
#            self.move_layer_top(setting.canvas['click_layer_id'])

    def map_layers_removed(self, layer_ids):
        """
        Unchecks image tab checkbox for layers removed and synchronizes
        image_layers in settings. Also ensures that
        setting.canvas['click_layer_id'] = None if the this layer is removed.

        Note that layers is a QStringList of layer IDs. A layer ID contains
        the layer name appended by the datetime added
        """
        logger.debug('Removed a map layer')
        for layer_id in layer_ids:
            # Remove from setting
            layer = QgsMapLayerRegistry.instance().mapLayers()[layer_id]
            if layer in setting.image_layers:
                setting.image_layers.remove(layer)

            # Find corresponding row in table
            rows_removed = [row for row, (image_name, fname) in
                            enumerate(itertools.izip(tsm.ts.image_names,
                                                     tsm.ts.filenames))
                            if image_name in layer_id or fname in layer_id]

            # Uncheck if needed
            for row in rows_removed:
                item = self.ctrl.image_table.item(row, 0)
                if item:
                    if item.checkState() == QtCore.Qt.Checked:
                        item.setCheckState(QtCore.Qt.Unchecked)

            # Check for click layer
            if setting.canvas['click_layer_id'] == layer_id:
                logger.debug('Removed click layer')
                setting.canvas['click_layer_id'] = None

# Signals
    def add_signals(self):
        """
        Add the signals to the options tab
        """
        # Options tab
        # Show/don't show where user clicked
        self.ctrl.cbox_showclick.stateChanged.connect(self.set_show_click)

        # Plot tab
        # Catch signal from plot options that we need to update
        self.ctrl.plot_options_changed.connect(self.update_display)
        # Catch signal to save the figure
        self.ctrl.plot_save_request.connect(self.save_plot)
        # Add layer from time series plot points
        self.ctrl.cbox_plotlayer.stateChanged.connect(self.set_plotlayer)
        # Connect/disconnect matplotlib event signal based on checkbox default
        self.set_plotlayer(self.ctrl.cbox_plotlayer.checkState())

        # Fmask mask values updated
        self.ctrl.mask_updated.connect(self.update_masks)

        # Symbology tab
        # Signal for having applied symbology settings
        self.ctrl.symbology_applied.connect(self.apply_symbology)

        # Image tab panel helpers for add/remove layers
        # NOTE: QGIS added "layersAdded" in 1.8(?) to replace some older
        #       signals. It looks like they intended on adding layersRemoved
        #       to replace layersWillBeRemoved/etc, but haven't gotten around
        #       to it... so we keep with the old signal for now
        #       http://www.qgis.org/api/classQgsMapLayerRegistry.html
        QgsMapLayerRegistry.instance().layersAdded.connect(
            self.map_layers_added)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(
            self.map_layers_removed)

        # Image tab panel
        self.ctrl.image_table.itemClicked.connect(self.get_tablerow_clicked)

### Slots for signals
# Slot for plot tab management
    @QtCore.pyqtSlot(int)
    def changed_tab(self, index):
        """ Updates which plot is currently being shown """
        if index == 0:
            self.active_plot = self.ts_plot
        elif index == 1:
            self.active_plot = self.doy_plot
        else:
            logger.error('You select a non-existent tab!? (#{i})'.format(
                i=index))

# Slots for map tool
    def fetch_data(self, pos):
        """ Receives QgsPoint, transforms into pixel coordinates, and begins
        thread that retrieves data
        """
        logger.info('Fetching data')
        if self.retriever.running is True:
            logger.warning('Currently fetching data. Please wait')
        else:
            # Convert position into pixel location
            px = int((pos[0] - tsm.ts.geo_transform[0]) /
                     tsm.ts.geo_transform[1])
            py = int((pos[1] - tsm.ts.geo_transform[3]) /
                     tsm.ts.geo_transform[5])

            if px < tsm.ts.x_size and py < tsm.ts.y_size:
                # Set pixel
                tsm.ts.set_px(px)
                tsm.ts.set_py(py)

                # Start fetching data and disable tool
#                self.retriever.running = True
                self.disable_tool.emit()

                # Init progress bar - updated by self.update_progress slot
                self.progress_bar = self.iface.messageBar().createMessage(
                    'Retrieving data for pixel x={x}, y={y}'.format(x=px,
                                                                    y=py))
                self.progress = QtGui.QProgressBar()
                self.progress.setValue(0)
                self.progress.setMaximum(tsm.ts.length)
                self.progress.setAlignment(QtCore.Qt.AlignLeft |
                                           QtCore.Qt.AlignVCenter)
                self.progress_bar.layout().addWidget(self.progress)
                self.cancel_retrieval = QtGui.QPushButton('Cancel')
                self.cancel_retrieval.pressed.connect(self.retrieval_cancel)
                self.progress_bar.layout().addWidget(self.cancel_retrieval)
                self.iface.messageBar().pushWidget(
                    self.progress_bar, self.iface.messageBar().INFO)

                # If we have custom options for TS, get them
                if self.ctrl.custom_form is not None and \
                        hasattr(tsm.ts, 'custom_controls'):

                    try:
                        options = self.ctrl.custom_form.get()
                        tsm.ts.set_custom_controls(options)
                    except:
                        self.ctrl.custom_form.reset()

                        self.retrieval_cancel()
                        self.iface.messageBar().pushMessage(
                            'Error',
                            'Could not use custom options for timeseries',
                            level=QgsMessageBar.CRITICAL,
                            duration=3)
                        return

                # Fetch pixel values
                self.retriever.get_ts_pixel()
                # self.retriever.start()

    @QtCore.pyqtSlot(int)
    def retrieval_progress_update(self, i):
        """ Update self.progress with value from DataRetriever """
        if self.retriever.running is True:
            self.progress.setValue(i + 1)
            # time.sleep(0.1)

    @QtCore.pyqtSlot()
    def retrieval_progress_complete(self):
        """ Updates plot and clears messages after DataRetriever completes """
        logger.info('Completed data retrieval!')
        self.iface.messageBar().clearWidgets()
        self.update_display()
        self.enable_tool.emit()

    @QtCore.pyqtSlot()
    def retrieval_cancel(self):
        """ Slot to cancel retrieval process """
        logger.warning('Canceling retrieval')
        self.retriever.running = False
#        self.retriever.terminate()
#        self.retriever.wait()
        self.enable_tool.emit()
        self.iface.messageBar().clearWidgets()

    def show_click(self, pos):
        """
        Receives QgsPoint and adds vector boundary of raster pixel clicked
        """
        # Record currently selected feature so we can restore it
        last_selected = self.iface.activeLayer()
        # Get raster pixel px py for pos
        gt = tsm.ts.geo_transform
        px = int((pos[0] - gt[0]) / gt[1])
        py = int((pos[1] - gt[3]) / gt[5])

        # Upper left coordinates of raster
        ulx = (gt[0] + px * gt[1] + py * gt[2])
        uly = (gt[3] + px * gt[4] + py * gt[5])

        # Create geometry
        gSquare = QgsGeometry.fromPolygon([[
            QgsPoint(ulx, uly),  # upper left
            QgsPoint(ulx + gt[1], uly),  # upper right
            QgsPoint(ulx + gt[1], uly + gt[5]),  # lower right
            QgsPoint(ulx, uly + gt[5])  # lower left
        ]])

        # Do we need to update or create the box?
        if setting.canvas['click_layer_id'] is not None:
            # Update to new row/column
            vlayer = QgsMapLayerRegistry.instance().mapLayers()[
                setting.canvas['click_layer_id']]
            vlayer.startEditing()
            pr = vlayer.dataProvider()
            attrs = pr.attributeIndexes()
            for feat in vlayer.getFeatures():
                vlayer.changeAttributeValue(feat.id(), 0, py)
                vlayer.changeAttributeValue(feat.id(), 1, px)
                vlayer.changeGeometry(feat.id(), gSquare)
                vlayer.updateExtents()
            vlayer.commitChanges()
            vlayer.triggerRepaint()
        else:
            # Create layer
            uri = 'polygon?crs=%s' % tsm.ts.projection
            vlayer = QgsVectorLayer(uri, 'Query', 'memory')
            pr = vlayer.dataProvider()
            vlayer.startEditing()
            pr.addAttributes([QgsField('row', QtCore.QVariant.Int),
                              QgsField('col', QtCore.QVariant.Int)])
            feat = QgsFeature()
            feat.setGeometry(gSquare)
            feat.setAttributes([py, px])
            pr.addFeatures([feat])
            # Symbology
            # Reference:
            # http://lists.osgeo.org/pipermail/qgis-developer/2011-April/013772.html
            props = {'color_border': '255, 0, 0, 255',
                     'style': 'no',
                     'style_border': 'solid',
                     'width': '0.40'}
            s = QgsFillSymbolV2.createSimple(props)
            vlayer.setRendererV2(QgsSingleSymbolRendererV2(s))

            # Commit and add
            vlayer.commitChanges()
            vlayer.updateExtents()

            vlayer_id = QgsMapLayerRegistry.instance().addMapLayer(vlayer).id()
            if vlayer_id:
                setting.canvas['click_layer_id'] = vlayer_id

        # Restore active layer
        self.iface.setActiveLayer(last_selected)

# Slots for options tab
    def set_show_click(self, state):
        """
        Updates showing/not showing of polygon where user clicked
        """
        if state == QtCore.Qt.Checked:
            setting.canvas['show_click'] = True
        elif state == QtCore.Qt.Unchecked:
            setting.canvas['show_click'] = False
            if setting.canvas['click_layer_id']:
                QgsMapLayerRegistry.instance().removeMapLayer(
                    setting.canvas['click_layer_id'])
                setting.canvas['click_layer_id'] = None

# Slots for time series table tab
    def get_tablerow_clicked(self, item):
        """
        If user clicks checkbox for image in image table, will add/remove
        image layer from map layers.
        """
        if item.column() != 0:
            return
        if item.checkState() == QtCore.Qt.Checked:
            self.add_map_layer(item.row())
        elif item.checkState() == QtCore.Qt.Unchecked:
            # If added is true and we now have unchecked, remove
            for layer in setting.image_layers:
                if tsm.ts.filepaths[item.row()] == layer.source():
                    QgsMapLayerRegistry.instance().removeMapLayer(layer.id())

# Symbology tab
    def apply_symbology(self, rlayers=None):
        """ Apply consistent raster symbology to all raster layers in time
        series
        """
        if rlayers is None:
            rlayers = setting.image_layers
        elif not isinstance(rlayers, list):
            rlayers = [rlayers]

        # Fetch band indexes
        r_band = setting.symbol['band_red']
        g_band = setting.symbol['band_green']
        b_band = setting.symbol['band_blue']

        for rlayer in rlayers:
            # Setup renderer
            r_ce = QgsContrastEnhancement(
                rlayer.dataProvider().dataType(r_band + 1))
            r_ce.setMinimumValue(setting.symbol['min'][r_band])
            r_ce.setMaximumValue(setting.symbol['max'][r_band])
            r_ce.setContrastEnhancementAlgorithm(setting.symbol['contrast'])
            r_ce.setContrastEnhancementAlgorithm(1)

            g_ce = QgsContrastEnhancement(
                rlayer.dataProvider().dataType(g_band + 1))
            g_ce.setMinimumValue(setting.symbol['min'][g_band])
            g_ce.setMaximumValue(setting.symbol['max'][g_band])
            g_ce.setContrastEnhancementAlgorithm(setting.symbol['contrast'])

            b_ce = QgsContrastEnhancement(
                rlayer.dataProvider().dataType(b_band + 1))
            b_ce.setMinimumValue(setting.symbol['min'][b_band])
            b_ce.setMaximumValue(setting.symbol['max'][b_band])
            b_ce.setContrastEnhancementAlgorithm(setting.symbol['contrast'])

            renderer = QgsMultiBandColorRenderer(rlayer.dataProvider(),
                                                 r_band + 1,
                                                 g_band + 1,
                                                 b_band + 1)
            renderer.setRedContrastEnhancement(r_ce)
            renderer.setGreenContrastEnhancement(g_ce)
            renderer.setBlueContrastEnhancement(b_ce)

            # Apply renderer
            rlayer.setRenderer(renderer)
            # Refresh & update symbology in legend
            if hasattr(rlayer, 'setCacheImage'):
                rlayer.setCacheImage(None)
            # Repaint and refresh
            rlayer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(rlayer)

# Slots for plot window signals
    def set_plotlayer(self, state):
        """
        Turns on or off the adding of map layers for a data point on plot
        """
        if state == QtCore.Qt.Checked:
            setting.plot['plot_layer'] = True
            self.ts_cid = self.ts_plot.fig.canvas.mpl_connect(
                'pick_event', self.plot_add_layer)
            self.doy_cid = self.doy_plot.fig.canvas.mpl_connect(
                'pick_event', self.plot_add_layer)
        elif state == QtCore.Qt.Unchecked:
            setting.plot['plot_layer'] = False
            self.ts_plot.fig.canvas.mpl_disconnect(self.ts_cid)
            self.doy_plot.fig.canvas.mpl_disconnect(self.doy_cid)

    def save_plot(self):
        """ Forwards plot save request to active plot """
        if self.active_plot is not None:
            success = self.active_plot.save_plot()
            if success is True:
                self.iface.messageBar().pushMessage('Info',
                                                    'Saved plot to file',
                                                    level=QgsMessageBar.INFO,
                                                    duration=2)

    def plot_add_layer(self, event):
        """
        Receives matplotlib event and adds layer for data point picked

        Note:   If the plot has symbology added, then it is using multiple
                lines. Instead of simply using event.ind, we need to get the
                line that was drawn (event.artist) to get the xdata, and pair
                the xdata[event.ind] with our TS's dates to get the correct
                index to add.

        Reference:
            http://matplotlib.org/users/event_handling.html
        """
        # Index of event for plotted data
        ind = np.array(event.ind)

        # ts_plot
        if isinstance(event.artist, mpl.lines.Line2D):
            # Get index from TS's dates for event index
            x_ind = np.where(tsm.ts.dates ==
                             event.artist.get_data()[0][ind][0])[0]
            self.add_map_layer(x_ind)
        # doy_plot
        elif isinstance(event.artist, mpl.collections.PathCollection):
            # Scatter indexes based on tsm.ts._data.compressed() so check if
            #   we've applied a mask and adjust index we add accordingly
            if isinstance(tsm.ts.get_data(setting.plot['mask']),
                          np.ma.core.MaskedArray):
                date = tsm.ts.dates[~tsm.ts.get_data().mask[
                    0, self.doy_plot.yr_range]][ind]
                ind = np.where(tsm.ts.dates == date)[0][0]
                self.add_map_layer(ind)
            else:
                self.add_map_layer(ind)
        else:
            logger.error('Unrecognized plot type. Cannot add image.')

    def calculate_scale(self):
        """
        Automatically calculate the min/max for time series plotting as the
        2nd and 98th percentile of each band's time series
        """
        # Get data with mask option
        data = tsm.ts.get_data(setting.plot['mask'])

        # Check for case where all data is masked
        if hasattr(data, 'mask'):
            if np.ma.compressed(data[0, :]).shape[0] == 0:
                logger.info('Cannot scale 100% masked data. Shape of data: ')
                logger.info(data[0, :].shape)
                return
        else:
            logger.debug('Data has no mask')

        setting.plot['min'] = np.array([
            np.percentile(np.ma.compressed(band), 2) - 500
            for band in data[:, ]])
        setting.plot['max'] = np.array([
            np.percentile(np.ma.compressed(band), 98) + 500
            for band in data[:, ]])

#        setting.plot['min'] = np.array([
#            np.percentile(np.ma.compressed(band), 2) for band in
#            data[:, ]])
#        setting.plot['max'] = np.array([
#            np.percentile(np.ma.compressed(band), 98) for band in
#            data[:, ]])

#        setting.plot['min'] = [min(0, np.min(band) *
#                                   (1 - setting.plot['scale_factor']))
#                           for band in tsm.ts.get_data()[:, ]]
#        setting.plot['max'] = [max(10000, np.max(band) *
#                                   (1 + setting.plot['scale_factor']))
#                           for band in tsm.ts.get_data()[:, ]]

    def disconnect(self):
        """
        Disconnect all signals added to various components
        """
        if self.configured:
            self.ctrl.symbology_applied.disconnect()
            self.ctrl.image_table.itemClicked.disconnect()
            self.ctrl.cbox_showclick.stateChanged.disconnect()
            self.ctrl.plot_options_changed.disconnect()
            self.ctrl.plot_save_request.disconnect()
            self.ctrl.cbox_plotlayer.stateChanged.disconnect()
            QgsMapLayerRegistry.instance().layersAdded.disconnect()
            QgsMapLayerRegistry.instance().layersWillBeRemoved.disconnect()
