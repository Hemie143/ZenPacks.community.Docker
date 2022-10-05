import logging

import Globals
from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration
from Products.ZenUtils.Utils import unused
unused(Globals)

log = logging.getLogger("zen.migrate")

remove_zproperties = [
    'zDockerPersistDuration',
    'zDockerContainerNotModeled',
]


class RemoveOldZProps(ZenPackMigration):
    version = Version(2, 0, 0)

    def migrate(self, pack):
        dmd = pack.dmd
        count = 0
        for prop in remove_zproperties:
            if dmd.Devices.hasProperty(prop):
                dmd.Devices._delProperty(prop)
                count += 1

        if count == 1:
            log.info("Removed %d obsolete zProperty", count)
        elif count:
            log.info("Removed %d obsolete zProperties", count)


RemoveOldZProps()
