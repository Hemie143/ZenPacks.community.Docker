from Products.ZenUtils.Utils import monkeypatch


@monkeypatch('Products.ZenModel.Device.Device')
def getContainers(self):
    return {c.id: {'model':c.last_seen_model, 'collect':c.last_seen_collect()} for c in self.dockerContainers()}
