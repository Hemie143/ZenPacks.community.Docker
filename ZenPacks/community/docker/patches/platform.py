from Products.ZenUtils.Utils import monkeypatch


@monkeypatch('Products.ZenModel.Device.Device')
def getContainers_lastSeen(self):
    return {c.id: c.last_seen_model for c in self.dockerContainers()}
