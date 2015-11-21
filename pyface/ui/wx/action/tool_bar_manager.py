#------------------------------------------------------------------------------
#
#  Copyright (c) 2005, Enthought, Inc.
#  All rights reserved.
#
#  This software is provided without warranty under the terms of the BSD
#  license included in enthought/LICENSE.txt and may be redistributed only
#  under the conditions described in the aforementioned license.  The license
#  is also available online at http://www.enthought.com/licenses/BSD.txt
#
#  Thanks for using Enthought open source!
#
#  Author: Enthought, Inc.
#
#------------------------------------------------------------------------------

""" The wx specific implementation of the tool bar manager.
"""

# Major package imports.
import wx

# Enthought library imports.
from traits.api import Bool, Enum, Instance, Str, Tuple

# Local imports.
from pyface.image_cache import ImageCache
from pyface.action.action_manager import ActionManager


class ToolBarManager(ActionManager):
    """ A tool bar manager realizes itself in errr, a tool bar control. """

    #### 'ToolBarManager' interface ###########################################

    # Is the tool bar enabled?
    enabled = Bool(True)

    # Is the tool bar visible?
    visible = Bool(True)

    # The size of tool images (width, height).
    image_size = Tuple((16, 16))

    # The toolbar name (used to distinguish multiple toolbars).
    name = Str('ToolBar')

    # The orientation of the toolbar.
    orientation = Enum('horizontal', 'vertical')

    # Should we display the name of each tool bar tool under its image?
    show_tool_names = Bool(True)

    # Should we display the horizontal divider?
    show_divider = Bool(False)

    #### Private interface ####################################################

    # Cache of tool images (scaled to the appropriate size).
    _image_cache = Instance(ImageCache)

    ###########################################################################
    # 'object' interface.
    ###########################################################################

    def __init__(self, *args, **traits):
        """ Creates a new tool bar manager. """

        # Base class contructor.
        super(ToolBarManager, self).__init__(*args, **traits)

        # An image cache to make sure that we only load each image used in the
        # tool bar exactly once.
        self._image_cache = ImageCache(self.image_size[0], self.image_size[1])

        return

    ###########################################################################
    # 'ToolBarManager' interface.
    ###########################################################################

    #### Trait change handlers ################################################
    #### Methods ##############################################################

    def create_tool_bar(self, parent, controller=None):
        """ Creates a tool bar. """

        # If a controller is required it can either be set as a trait on the
        # tool bar manager (the trait is part of the 'ActionManager' API), or
        # passed in here (if one is passed in here it takes precedence over the
        # trait).
        if controller is None:
            controller = self.controller

        # Determine the wx style for the tool bar based on any optional
        # settings.
        style = wx.NO_BORDER | wx.TB_FLAT | wx.CLIP_CHILDREN

        if self.show_tool_names:
            style |= wx.TB_TEXT

        if self.orientation == 'horizontal':
            style |= wx.TB_HORIZONTAL

        else:
            style |= wx.TB_VERTICAL

        if not self.show_divider:
            style |= wx.TB_NODIVIDER

        # Create the control.
        tool_bar = _ToolBar(self, parent, -1, style=style)

        # fixme: Setting the tool bitmap size seems to be the only way to
        # change the height of the toolbar in wx.
        tool_bar.SetToolBitmapSize(self.image_size)

        # Add all of items in the manager's groups to the tool bar.
        self._wx_add_tools(parent, tool_bar, controller)

        # Make the tools appear in the tool bar (without this you will see
        # nothing!).
        tool_bar.Realize()

        # fixme: Without the following hack,  only the first item in a radio
        # group can be selected when the tool bar is first realised 8^()
        self._wx_set_initial_tool_state(tool_bar)

        return tool_bar

    ###########################################################################
    # Private interface.
    ###########################################################################

    def _wx_add_tools(self, parent, tool_bar, controller):
        """ Adds tools for all items in the list of groups. """

        previous_non_empty_group = None
        for group in self.groups:
            if len(group.items) > 0:
                # Is a separator required?
                if previous_non_empty_group is not None and group.separator:
                    tool_bar.AddSeparator()

                previous_non_empty_group = group

                # Create a tool bar tool for each item in the group.
                for item in group.items:
                    item.add_to_toolbar(
                        parent,
                        tool_bar,
                        self._image_cache,
                        controller,
                        self.show_tool_names
                    )

        return

    def _wx_set_initial_tool_state(self, tool_bar):
        """ Workaround for the wxPython tool bar bug.

        Without this,  only the first item in a radio group can be selected
         when the tool bar is first realised 8^()

        """

        for group in self.groups:
            checked = False
            for item in group.items:
                # If the group is a radio group,  set the initial checked state
                # of every tool in it.
                if item.action.style == 'radio':
                    if item.control_id is not None:
                        # Only set checked state if control has been created.
                        # Using extra_actions of tasks, it appears that this
                        # may be called multiple times.
                        tool_bar.ToggleTool(item.control_id, item.action.checked)
                        checked = checked or item.action.checked

                # Every item in a radio group MUST be 'radio' style, so we
                # can just skip to the next group.
                else:
                    break

            # We get here if the group is a radio group.
            else:
                # If none of the actions in the group is specified as 'checked'
                # we will check the first one.
                if not checked and len(group.items) > 0:
                    group.items[0].action.checked = True

        return

from pyface.wx.aui import aui
if aui is not None:
    toolbarobject = aui.AuiToolBar
else:
    toolbarobject = wx.ToolBar

class _ToolBar(toolbarobject):
    """ The toolkit-specific tool bar implementation. """

    ###########################################################################
    # 'object' interface.
    ###########################################################################

    def __init__(self, tool_bar_manager, parent, id, style):
        """ Constructor. """

        toolbarobject.__init__(self, parent, -1, style=style)

        # Listen for changes to the tool bar manager's enablement and
        # visibility.
        self.tool_bar_manager = tool_bar_manager

        self.tool_bar_manager.on_trait_change(
            self._on_tool_bar_manager_enabled_changed, 'enabled'
        )

        self.tool_bar_manager.on_trait_change(
            self._on_tool_bar_manager_visible_changed, 'visible'
        )
        
        # we need to defer hiding tools until first time Realize is called so
        # we can get the correct order of the toolbar for reinsertion at the
        # correct position
        self.initially_hidden_tool_ids = []
        
        # map of tool ids to a tuple: position in full toolbar and the
        # ToolBarTool itself.  Can't keep a weak reference here because once
        # removed from the toolbar the item would be garbage collected.
        self.tool_map = {}

        return
    
    def Realize(self):
        if len(self.tool_map) == 0:
            for pos in range(self.GetToolsCount()):
                tool = self.GetToolByPos(pos)
                self.tool_map[tool.GetId()] = (pos, tool)
        toolbarobject.Realize(self)
        if len(self.initially_hidden_tool_ids) > 0:
            for tool_id in self.initially_hidden_tool_ids:
                self.RemoveTool(tool_id)
            self.initially_hidden_tool_ids = []
        self.ShowTool = self.ShowToolPostRealize
    
    def ShowTool(self, tool_id, state):
        """Used before realization to flag which need to be initially hidden
        """
        if not state:
            self.initially_hidden_tool_ids.append(tool_id)
    
    def ShowToolPostRealize(self, tool_id, state):
        """Normal ShowTool method, activated after first call to Realize
        """
        tool = self.FindById(tool_id)
        if state and tool is None:
            self.InsertToolInOrder(tool_id)
            self.EnableTool(tool_id, True)
            self.Realize()
            # Update the toolbar in the AUI manager to force toolbar resize
            wx.CallAfter(self.tool_bar_manager.controller.task.window._aui_manager.Update)
        elif not state and tool is not None:
            self.RemoveTool(tool_id)
            # Update the toolbar in the AUI manager to force toolbar resize
            wx.CallAfter(self.tool_bar_manager.controller.task.window._aui_manager.Update)
        
    def InsertToolInOrder(self, tool_id):
        orig_pos, tool = self.tool_map[tool_id]
        for pos in range(self.GetToolsCount()):
            existing_tool = self.GetToolByPos(pos)
            existing_id = existing_tool.GetId()
            existing_orig_pos, _ = self.tool_map[tool_id]
            if existing_orig_pos > orig_pos:
                break
        self.InsertToolItem(pos+1, tool)

    ###########################################################################
    # Trait change handlers.
    ###########################################################################

    def _on_tool_bar_manager_enabled_changed(self, obj, trait_name, old, new):
        """ Dynamic trait change handler. """

        obj.controller.task.window._wx_enable_tool_bar(self, new)

        return

    def _on_tool_bar_manager_visible_changed(self, obj, trait_name, old, new):
        """ Dynamic trait change handler. """

        obj.controller.task.window._wx_show_tool_bar(self, new)

        return

#### EOF ######################################################################
