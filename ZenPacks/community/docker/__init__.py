import os
import logging

from ZenPacks.zenoss.ZenPackLib import zenpacklib
from Products.ZenUtils.Utils import monkeypatch

CFG = zenpacklib.load_yaml([os.path.join(os.path.dirname(__file__), "zenpack.yaml")], verbose=False, level=30)
schema = CFG.zenpack_module.schema

log = logging.getLogger('zen.DockerInit')

@monkeypatch("Products.ZenModel.Device.Device")
def getContainers(self):
    # TODO: clean up logging
    log.info('Starting getContainers*********************************************************************************')
    cc = self.dockerContainers()[0]
    log.info('cc: {}'.format(cc))
    log.info('cc.id: {}'.format(cc.id))
    log.info('cc.last_seen_model: {}'.format(cc.last_seen_model))
    log.info('cc.last_seen_collect: {}'.format(cc.last_seen_collect()))
    test = {c.id: {'model':c.last_seen_model, 'collect':c.last_seen_collect()} for c in self.dockerContainers()}
    log.info('cc.test: {}'.format(test))
    return test

# Patch last to avoid import recursion problems.
# TODO: Move patch
'''
from Products.ZenUtils.Utils import unused
from . import patches
unused(patches)
'''