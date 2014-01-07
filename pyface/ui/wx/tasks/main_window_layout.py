# Standard library imports.
from itertools import combinations
import logging

# System library imports.
#from pyface.qt import QtCore, QtGui

# Enthought library imports.
from traits.api import Any, HasTraits

# Local imports.
from dock_pane import AREA_MAP, INVERSE_AREA_MAP
from pyface.tasks.task_layout import LayoutContainer, PaneItem, Tabbed, \
     Splitter, HSplitter, VSplitter

# Contants.
#ORIENTATION_MAP = { 'horizontal' : QtCore.Qt.Horizontal,
#                    'vertical': QtCore.Qt.Vertical }

# Logging.
logger = logging.getLogger(__name__)


class MainWindowLayout(HasTraits):
    """ A class for applying declarative layouts to a QMainWindow.
    """

    ###########################################################################
    # 'MainWindowLayout' interface.
    ###########################################################################

    def get_layout(self, layout, window):
        """ Get the layout by adding sublayouts to the specified DockLayout.
        """
        print "WX: get_layout: %s" % layout
        layout.perspective = window._aui_manager.SavePerspective()
        print "WX: get_layout: saving perspective %s" % layout.perspective

    def set_layout(self, layout, window):
        """ Applies a DockLayout to the window.
        """
        print "WX: set_layout: %s" % layout
        
        if hasattr(layout, "perspective"):
            self._set_layout_from_aui(layout, window)
            return

        # Perform the layout. This will assign fixed sizes to the dock widgets
        # to enforce size constraints specified in the PaneItems.
        for name, direction in AREA_MAP.iteritems():
            sublayout = getattr(layout, name)
            if sublayout:
                self.set_layout_for_area(sublayout, direction,
                                         _toplevel_call=False)

        # Add all panes not assigned an area by the TaskLayout.
        mgr = window._aui_manager
        for dock_pane in self.state.dock_panes:
            info = mgr.GetPane(dock_pane.pane_name)
            if not info.IsOk():
                print "WX: set_layout: managing pane %s" % dock_pane.pane_name
                dock_pane.add_to_manager()
            else:
                print "WX: set_layout: arleady managed pane: %s" % dock_pane.pane_name
    
    def _set_layout_from_aui(self, layout, window):
        # The central pane will have already been added, but we need to add all
        # of the dock panes to the manager before the call to LoadPerspective
        print "WX: _set_layout_from_aui: using saved perspective"
        for dock_pane in self.state.dock_panes:
            print "WX: adding dock pane %s" % dock_pane.id
            dock_pane.add_to_manager()
        print "WX: _set_layout_from_aui: restoring perspective %s" % layout.perspective
        window._aui_manager.LoadPerspective(layout.perspective)
        

    def set_layout_for_area(self, layout, direction,
                            _toplevel_added=False, _toplevel_call=True):
        """ Applies a LayoutItem to the specified dock area.
        """
        # If we try to do the layout bottom-up, Qt will become confused. In
        # order to do it top-down, we have know which dock widget is
        # "effectively" top level, requiring us to reach down to the leaves of
        # the layout. (This is really only an issue for Splitter layouts, since
        # Tabbed layouts are, for our purposes, leaves.)
        print "WX: set_layout_for_area: %s" % INVERSE_AREA_MAP[direction]
        
        if isinstance(layout, PaneItem):
            if not _toplevel_added:
                dock_pane = self._get_dock_pane(layout)
                dock_pane.dock_area = INVERSE_AREA_MAP[direction]
                print "WX: layout size (%d,%d)" % (layout.width, layout.height)
                dock_pane.add_to_manager()
        
        elif isinstance(layout, Tabbed):
            active_pane = first_pane = None
            for item in layout.items:
                dock_pane = self._get_dock_pane(item)
                dock_pane.dock_area = INVERSE_AREA_MAP[direction]
                if item.id == layout.active_tab:
                    active_pane = dock_pane
                dock_pane.add_to_manager(first_pane)
                if not first_pane:
                    first_pane = dock_pane

            # Activate the appropriate tab, if possible.
            if not active_pane:
                # By default, Qt will activate the last widget.
                active_pane = first_pane
            if active_pane:
                # set pane is active in the AUI notebook (somehow)
                pass

        elif isinstance(layout, Splitter):
            # Perform top-level splitting as per above comment.
            orient = ORIENTATION_MAP[layout.orientation]
            prev_widget = None
            for item in layout.items:
                widget = self._prepare_toplevel_for_item(item)
                if not widget:
                    continue
                if prev_widget:
                    self.control.splitDockWidget(prev_widget, widget, orient)
                elif not _toplevel_added:
                    self.control.addDockWidget(q_dock_area, widget)
                prev_widget = widget
                widget.show()

            # Now we can recurse.
            for i, item in enumerate(layout.items):
                self.set_layout_for_area(item, q_dock_area,
                    _toplevel_added=True, _toplevel_call=False)
                
        else:
            raise MainWindowLayoutError("Unknown layout item %r" % layout)

        # Remove the fixed sizes once Qt activates the layout.
        if _toplevel_call:
            QtCore.QTimer.singleShot(0, self._reset_fixed_sizes)

    ###########################################################################
    # 'MainWindowLayout' abstract interface.
    ###########################################################################

    def _get_dock_widget(self, pane):
        """ Returns the QDockWidget associated with a PaneItem.
        """
        raise NotImplementedError

    def _get_pane(self, dock_widget):
        """ Returns a PaneItem for a QDockWidget.
        """
        raise NotImplementedError

    def _get_dock_pane(self, pane):
        """ Returns the DockPane associated with a PaneItem.
        """
        for dock_pane in self.state.dock_panes:
            if dock_pane.id == pane.id:
                return dock_pane
        return None

    ###########################################################################
    # Private interface.
    ###########################################################################

    def _get_division_orientation(self, one, two, splitter=False):
        """ Returns whether there is a division between two visible QWidgets.

        Divided in context means that the widgets are adjacent and aligned along
        the direction of the adjaceny.
        """
        united = one.united(two)
        if splitter:
            sep = self.control.style().pixelMetric(
                QtGui.QStyle.PM_DockWidgetSeparatorExtent, None, self.control)
            united.adjust(0, 0, -sep, -sep)
            
        if one.x() == two.x() and one.width() == two.width() and \
               united.height() == one.height() + two.height():
            return QtCore.Qt.Horizontal
        
        elif one.y() == two.y() and one.height() == two.height() and \
                 united.width() == one.width() + two.width():
            return QtCore.Qt.Vertical
        
        return 0

    def _get_tab_bar(self, dock_widget):
        """ Returns the tab bar associated with the given QDockWidget, or None
        if there is no tab bar.
        """
        dock_geometry = dock_widget.geometry()
        for child in self.control.children():
            if isinstance(child, QtGui.QTabBar) and child.isVisible():
                geometry = child.geometry()
                if self._get_division_orientation(dock_geometry, geometry):
                    return child
        return None

    def _prepare_pane(self, dock_widget, include_sizes=True):
        """ Returns a sized PaneItem for a QDockWidget.
        """
        pane = self._get_pane(dock_widget)
        if include_sizes:
            pane.width = dock_widget.widget().width()
            pane.height = dock_widget.widget().height()
        return pane

    def _prepare_toplevel_for_item(self, layout):
        """ Returns a sized toplevel QDockWidget for a LayoutItem.
        """
        if isinstance(layout, PaneItem):
            dock_widget = self._get_dock_widget(layout)
            if dock_widget is None:
                logger.warning('Cannot retrieve dock widget for pane %r'
                               % layout.id)
            else:
                if layout.width > 0:
                    dock_widget.widget().setFixedWidth(layout.width)
                if layout.height > 0:
                    dock_widget.widget().setFixedHeight(layout.height)
            return dock_widget
        
        elif isinstance(layout, LayoutContainer):
            return self._prepare_toplevel_for_item(layout.items[0])
        
        else:
            raise MainWindowLayoutError("Leaves of layout must be PaneItems")



class MainWindowLayoutError(ValueError):
    """ Exception raised when a malformed LayoutItem is passed to the
    MainWindowLayout.
    """
    pass
