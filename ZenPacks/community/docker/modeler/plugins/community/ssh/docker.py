"""Models locations using the National Weather Service API. 02"""

# stdlib Imports
import logging
import os
import re
import time

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue

from ZenPacks.community.Docker.lib.sshclient import SSHClient
from ZenPacks.community.Docker.lib.parsers import get_docker_data
from ZenPacks.community.Docker.modeler.plugins.modeler import model_ps_containers, model_remaining_containers, \
    model_placeholder_container

log = logging.getLogger('zen.DockerPlugin')


class docker(PythonPlugin):
    """docker containers modeler plugin."""

    requiredProperties = (
        'zCommandUsername',
        'zCommandPassword',
        'zCommandPort',
        'zCommandCommandTimeout',
        'zKeyPath',
        'zDockerPersistDuration',
        'getContainers_lastSeen',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    clients = {}

    commands = {
        'version': 'docker -v',
        'containers': 'sudo docker ps --no-trunc',
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
        for item, cmd in self.commands.items():
            try:
                response = yield client.run(cmd, timeout=timeout)
                results[item] = response
            except Exception, e:
                log.error("{} {} docker modeler error: {}".format(device.id, self.name(), e))
        returnValue(results)

    def process(self, device, results, log):
        """Process results. Return iterable of datamaps or None."""
        current_containers = device.getContainers_lastSeen
        log.debug('--- Current containers: {}'.format(current_containers))

        rm = []
        if 'containers' in results:
            try:
                dockerPersistDuration = int(device.zDockerPersistDuration)
            except Exception:
                dockerPersistDuration = 24
            container_maps = self.model_containers(results['containers'],
                                                   current_containers,
                                                   dockerPersistDuration,
                                                   )
            rm.extend(container_maps)
        return rm

    def model_containers(self, result, current_containers, dockerPersistDuration):
        if result.exitCode > 0:
            log.error('Could not list containers (exitcode={}) - Error: {}'.format(result.exitCode, result.stderr))

        # Model the containers
        now = int(time.time())
        time_expiry = now - int(dockerPersistDuration * 3600)
        rm = []
        containers_maps = []
        remaining_instances = list(current_containers.keys())
        log.debug('--- Remaining instances: {}'.format(len(remaining_instances)))

        # Model the containers detected with "docker ps"
        containers_ps_data = get_docker_data(result.output, 'PS')
        containers_maps.extend(model_ps_containers(containers_ps_data))
        log.debug('--- Modeled {} containers with docker ps'.format(len(containers_maps)))

        # Remove found containers from remaining_instances
        ps_instances = ['container_{}'.format(c["CONTAINER ID"]) for c in containers_ps_data]
        remaining_instances = set(remaining_instances) - set(ps_instances)
        log.debug('--- Remaining {} instances after docker ps'.format(remaining_instances))

        # Check if remaining instances have expired
        containers_maps.extend(model_remaining_containers(remaining_instances, current_containers, time_expiry))
        log.debug('--- Modeled {} containers in total after keeping old instances'.format(len(containers_maps)))

        # If no container is present, create a placeholder so that the datasource is running
        if len(containers_maps) == 0:
            containers_maps.append(model_placeholder_container())

        rm.append(RelationshipMap(compname='',
                                  relname='dockerContainers',
                                  modname='ZenPacks.community.Docker.DockerContainer',
                                  objmaps=containers_maps,
                                  ))
        return rm
