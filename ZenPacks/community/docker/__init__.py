import os

from ZenPacks.zenoss.ZenPackLib import zenpacklib
from Products.ZenUtils.Utils import monkeypatch
from Products.ZenUtils.Utils import unused
from . import patches

CFG = zenpacklib.load_yaml([os.path.join(os.path.dirname(__file__), "zenpack.yaml")], verbose=False, level=30)
schema = CFG.zenpack_module.schema

# Patch last to avoid import recursion problems.
unused(patches)
