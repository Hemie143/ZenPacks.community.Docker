# stdlib Imports
import logging

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
# Twisted Imports
from twisted.internet.defer import returnValue, inlineCallbacks

# Setup logging
log = logging.getLogger('zen.Dockercontainers')

class stats(PythonDataSourcePlugin):

    @inlineCallbacks
    def collect(self, config):
        yield True
        returnValue(0)

    def onSuccess(self, results, config):
        log.debug('Success - results is {}'.format(results))
        data = self.new_data()
        return data
