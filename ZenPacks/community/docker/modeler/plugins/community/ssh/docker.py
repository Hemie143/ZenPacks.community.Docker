"""Models locations using the National Weather Service API. 02"""

# stdlib Imports
import logging
import os
import re

# Zenoss Imports
from Products.ZenUtils.Utils import prepId
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue

from ZenPacks.community.Docker.lib.sshclient import SSHClient
from ZenPacks.community.Docker.lib.utils import transform_valid_regex
from ZenPacks.community.Docker.modeler.plugins.modeler import generate_container_others, generate_container_total

log = logging.getLogger('zen.DockerPlugin')


class docker(PythonPlugin):
    """docker containers modeler plugin."""

    requiredProperties = (
        'zCommandUsername',
        'zCommandPassword',
        'zCommandPort',
        'zCommandCommandTimeout',
        'zKeyPath',
        'zDockerContainerModeled',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    clients = {}

    commands = {
        'version': 'docker -v',
        # 'containers': 'sudo docker ps --no-trunc',
    }

    @classmethod
    def getClient(cls, config):
        h = config['hostname']
        if h in cls.clients:
            log.debug('Using cached sshclient connection for {}:{}'.format(h, config['port']))
            return cls.clients[h]
        else:
            log.debug('Creating new sshclient connection for {}:{}'.format(h, config['port']))
            cls.clients[h] = SSHClient(config)
            try:
                cls.clients[h].connect()
            except Exception:
                pass
        return cls.clients[h]

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred."""
        log.info('Collecting docker containers for device {}'.format(device.id))

        if (device.zCommandUsername == ''):
            log.warn('zCommandUsername is empty.')
            returnValue(None)
        if (device.zCommandPassword == ''):
            log.warn('zCommandPassword is empty, trying key authentication using %s', device.zKeyPath)
        keyPath = os.path.expanduser(device.zKeyPath)
        if os.path.isfile(keyPath):
            log.info('SSH key found.')
        else:
            if device.zCommandPassword is None or device.zCommandPassword == '':
                returnValue(None)

        options = {'hostname': str(device.manageIp),
                   'port': device.zCommandPort,
                   'user': device.zCommandUsername,
                   'password': device.zCommandPassword,
                   'identities': [keyPath],
                   'buffersize': 32768,
                   }

        timeout = device.zCommandCommandTimeout
        if timeout:
            timeout = int(timeout)
        else:
            timeout = 15

        client = self.getClient(options)
        log.debug('client: {}'.format(type(client)))
        log.debug('client: {}'.format(client))

        results = {}
        # TODO: The command is not required, but probably a simple check on docker presence.
        for item, cmd in self.commands.items():
            try:
                response = yield client.run(cmd, timeout=timeout)
                results[item] = response
            except Exception, e:
                log.error("{} {} docker modeler error: {}".format(device.id, self.name(), e))
        returnValue(results)


    def process(self, device, results, log):
        """Process results. Return iterable of datamaps or None."""
        # TODO: Clean up process
        rm = []
        if 'version' in results:
            container_maps = self.model_containers(device, results['version'])
            rm.extend(container_maps)
        return rm

    @staticmethod
    def validate_modeling_regex(device):
        log.debug('--- device: {}'.format(device))
        zDockerContainerModeled = getattr(device, 'zDockerContainerModeled', [])
        model_list = transform_valid_regex(zDockerContainerModeled)
        return model_list

    def model_containers(self, device, result):
        # [{'STATUS': 'Up 52 seconds', 'CREATED': '53 seconds ago', 'IMAGE': 'docker.fednot.be:5000/monorepo-install:FRON-FFM-6191', 'COMMAND': '"/usr/local/bin/mvn-entrypoint.sh ./tools/bamboo/build.sh 6191 NA NA AX23C0LVSTUAEGXJMY36 C0vp5TmSHLxoQrL+qy=7B0dpYGkbqHzNp9olzG7m 2 2"', 'NAMES': 'monorepo-build-FRON-FFM-BUIL2-6191-1664443247', 'CONTAINER ID': '5b16dcbe5ee1e9465856f166995d31f51c40ef98628c1914bbfc77b568215ada', 'PORTS': ''}]
        # TODO: Result is probably not required
        if result.exitCode > 0:
            log.error('Could not list containers (exitcode={}) - Error: {}'.format(result.exitCode, result.stderr))

        model_list = self.validate_modeling_regex(device)
        log.debug('model_list: {}'.format(model_list))

        # Model the containers
        rm = []
        containers_maps = []

        # Model the containers based on the model list
        # TODO: What if some pattern are redundant ? (e.g. "cer-.*" and "cer-bri-.*")
        for name in model_list:
            if not name:
                continue
            try:
                re.compile(name)
            except:
                log.warning('Invalid regex in zDockerContainerModeled: {}'.format(name))
                continue
            c_instance = ObjectMap()
            instance_id = prepId('container_{}'.format(name))
            log.debug('id: **{}**'.format(instance_id))
            c_instance.id = instance_id
            c_instance.title = name
            c_instance.regex = name
            log.debug('c_instance: {}'.format(c_instance))
            containers_maps.append(c_instance)

        # Add instance for containers not included
        containers_maps.append(generate_container_others())

        # Add instance for grand total
        containers_maps.append(generate_container_total())

        rm.append(RelationshipMap(compname='',
                                  relname='dockerContainerVolatiles',
                                  modname='ZenPacks.community.Docker.DockerContainerVolatile',
                                  objmaps=containers_maps,
                                  ))
        return rm
