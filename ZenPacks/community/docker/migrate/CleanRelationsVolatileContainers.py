import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger('zen.migrate')


class CleanRelationsVolatileContainers(ZenPackMigration):
    version = Version(2, 0, 0)

    def migrate(self, pack):
        dc = pack.dmd.Devices.Server.SSH
        log.info('Clean up old relationships')

        '''
        zcat = pack.dmd.global_catalog(meta_type='DockerContainer')
        log.info(zcat)
        for z in zcat:
            try:
                #  ['__class__', '__contains__', '__delattr__', '__dict__', '__doc__', '__format__', '__getattribute__', '__getstate__', '__hash__', '__implemented__', '__init__', '__module__', '__new__', '__of__', '__providedBy__', '__provides__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__setstate__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_data', '_unrestrictedGetObject', 'adminUserIds', 'allowedRolesAndUsers', 'collector', 'collectors', 'decimal_ipAddress', 'description', 'deviceClassPath', 'deviceId', 'deviceOrganizers', 'firstDecimalIp', 'getObject', 'getPath', 'getRID', 'has_key', 'hwManufacturer', 'hwModel', 'id', 'idxs', 'interfaceId', 'ipAddress', 'ipAddressAsText', 'ipAddressId', 'lanId', 'lastDecimalIp', 'macAddresses', 'macaddress', 'meta_type', 'modelindex_uid', 'monitored', 'name', 'networkId', 'objectImplements', 'osManufacturer', 'osModel', 'path', 'priority', 'productClassId', 'productionState', 'pythonClass', 'searchExcerpt', 'searchIcon', 'searchKeywords', 'serialNumber', 'tagNumber', 'text_ipAddress', 'to_dict', 'tx_state', 'uid', 'uuid', 'zProperties']
                log.info(z)
                log.info(z.deviceClassPath)
                log.info(z.deviceId)
                log.info(z.id)
                log.info(z.name)
                # log.info(dir(z))
                ob = z.getOBject()
                log.info(ob)
            except Exception:
                log.warn('Problem retrieving component from catalog')
        '''

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
        '''
        log.info('Device {} has {} dockerContainers'.format(d.id, len(d.dockerContainers())))
        log.info('Device {} has {} dockerContainers'.format(d.id, len(d.dockerContainers())))
        '''



CleanRelationsVolatileContainers()