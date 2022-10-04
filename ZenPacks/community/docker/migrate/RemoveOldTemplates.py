"""Removes old monitoring templates.
Version 1.x of this ZenPack installed the following monitoring templates
that are no longer needed in the /Devices/Server/SSH device class.
* DockerContainer
"""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger("zen.migrate")

OLD_TEMPLATES = [
    "DockerContainer",
]


class RemoveOldTemplates(ZenPackMigration):
    version = Version(2, 0, 0)

    def migrate(self, pack):
        # devices = pack.getDmdRoot("Devices/Server/SSH")
        dc = pack.dmd.Devices.Server.SSH
        log.info("Removing old Docker monitoring template")
        for template in OLD_TEMPLATES:
            try:
                dc.manage_deleteRRDTemplates(ids=[template])
            except Exception:
                pass
