from Products.ZenUtils.Utils import monkeypatch


@monkeypatch('Products.ZenModel.Device.Device')
def getContainers(self):
    return {c.id: c.last_seen for c in self.dockerContainers()}