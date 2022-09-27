import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger('zen.migrate')


class CleanRelationsVolatileContainers(ZenPackMigration):
    version = Version(2, 0, 0)

    def migrate(self, pack):
        dc = pack.dmd.Devices.Server.SSH
        r_count = 0
        for d in dc.getSubDevicesGen():
            if hasattr(d, 'dockerContainers'):
                log.info('Device {} has {} dockerContainers'.format(d.id, len(d.dockerContainers())))
                d._delObject('dockerContainers')
                r_count += 1
                log.info('Device {} check: {}'.format(d.id, hasattr(d, 'dockerContainers')))

        log.info('Cleaned up relationships for {} devices'.format(r_count))
        '''
        log.info('Device {} has {} dockerContainers'.format(d.id, len(d.dockerContainers())))
        for dockerContainer in d.dockerContainers():
            log.info('Device {} has dockerContainers relationship: {}'.format(d.id, dockerContainer.id))
            # d._delObject(dockerContainer.id)
        log.info('Device {} has {} dockerContainers'.format(d.id, len(d.dockerContainers())))
        '''



CleanRelationsVolatileContainers()