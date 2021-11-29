from Products.ZenUtils.Utils import monkeypatch


@monkeypatch('Products.ZenModel.Device.Device')
def getContainers(self):
    return {c.id: {'model':c.last_seen_model, 'collect':c.last_seen_collect()} for c in self.dockerContainers()}

def getContainers_lastSeen(self):
    return {c.id: c.last_seen_model for c in self.dockerContainers()}

# This is a test
# test 2
# test 3
