import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger('zen.migrate')

# TODO: Maybe to remove whole migration script. Not sure it's necessary and it doesn't prevent messages like:
# zen.Relations: Ignoring unresolvable object '<persistent broken ZenPacks.community.Docker.DockerContainer.DockerContainer instance '\x00\x00\x00\x00\x00\x1f)\x01'>'
class CleanRelationsVolatileContainers(ZenPackMigration):
    version = Version(2, 0, 0)

    def migrate(self, pack):
        dc = pack.dmd.Devices.Server.SSH
        log.info('Clean up old relationships')
        r_count = 0
        c_count = 0
        for d in dc.getSubDevicesGen():
            if hasattr(d, 'dockerContainers'):
                components = d.dockerContainers()
                if len(components) > 0 :

                    log.info('Device {} has {} dockerContainers'.format(d.id, len(components)))
                    for dockerContainer in d.dockerContainers():
                        log.info('Device {} has dockerContainers relationship: {}'.format(d.id, dockerContainer.id))
                        log.info(dockerContainer)
                        d.dockerContainers._delObject(dockerContainer.id)
                        # d.getPrimaryParent()._delObject(object.id)

                        c_count += 1
                # d.manage_deleteObjects(['dockerContainers'])
                d._delObject('dockerContainers')
                r_count += 1
                log.info('Device {} check: {}'.format(d.id, hasattr(d, 'dockerContainers')))

        log.info('Cleaned up {} components and relationships for {} devices'.format(c_count, r_count))

CleanRelationsVolatileContainers()