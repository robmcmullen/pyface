# Standard library imports.
import logging

import os

# Logger.
logger = logging.getLogger(__name__)

requested = ""
if 'ETS_WX_AUI' in os.environ:
    requested = os.environ['ETS_WX_AUI']

aui = None
try:
    if requested.lower() == "wx":
        from wx import aui
    elif requested.lower() == "agw":
        from wx.lib.agw import aui
except ImportError:
    logger.warn('Requested AUI toolkit (ETS_WX_AUI=%s) not available', requested)

if aui is None:
    # If nothing specified, use the included copy of wx.lib.agw.aui that
    # includes some bug fixes.  Upstream does have copies of these bug fixes,
    # but they haven't been propagated to any new releases of wxPython.
    from pyface.wx.agw import aui
