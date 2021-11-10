import os
from ZenPacks.zenoss.ZenPackLib import zenpacklib
from Products.ZenUtils.Utils import monkeypatch

CFG = zenpacklib.load_yaml([os.path.join(os.path.dirname(__file__), "zenpack.yaml")], verbose=False, level=30)
schema = CFG.zenpack_module.schema


@monkeypatch("Products.ZenModel.Device.Device")
def getContainers(self):
    return {c.id: c.last_seen for c in self.dockerContainers()}
