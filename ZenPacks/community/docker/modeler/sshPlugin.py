
from twisted.internet.defer import inlineCallbacks, returnValue

class sshPlugin(object):

    def __init__(self, client, timeout):
        self.client = client
        self.timeout = timeout

    @inlineCallbacks
    def getResults(self):
        # timeOutValue = 15
        try:
            timeOutValue = int(str(self.timeout))
        except:
            timeOutValue = 15

        d = yield self.client.run('docker -v', timeout=timeOutValue)
        returnValue(d)
