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
            except:
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
        log.debug('results: {}'.format(results))
        returnValue(results)

    def process(self, device, results, log):
        """Process results. Return iterable of datamaps or None."""

        # current_containers = {}
        current_containers = device.getContainers_lastSeen
        log.debug('--- Current containers: {}'.format(current_containers))

        rm = []
        if 'containers' in results:
            try:
                dockerPersistDuration = int(device.zDockerPersistDuration)
            except:
                dockerPersistDuration = 24
            container_maps = self.model_containers(results['containers'],
                                                   current_containers,
                                                   dockerPersistDuration,
                                                   )
            rm.extend(container_maps)
        return rm

    def model_containers(self, result, current_containers, dockerPersistDuration):
        # TODO: use parser in lib
        # TODO: clean up code
        # TODO: modeler should at least create one placeholder instance, otherwise the collector won't run
        '''
        expected_columns = set([
            "CONTAINER ID",
            "IMAGE",
            "COMMAND",
            "CREATED",
            "PORTS",
            "NAMES",
            "STATUS",
        ])
        '''
        # log.debug('containers result: {}'.format(result.__dict__))
        if result.exitCode > 0:
            log.error('Could not list containers (exitcode={}) - Error: {}'.format(result.exitCode, result.stderr))

        '''
        output = result.output.strip().splitlines()
        if not output or len(output) <= 1:
            log.warning('Could not list containers - Result: {}'.format(result.output))

        header_line = output[0]
        container_lines = output[1:]
        columns = re.split(r' {2,}', header_line)
        log.debug('columns : {}'.format(columns))
        if not set(expected_columns).issubset((columns)):
            log.error('Missing column(s) while listing containers: {}'.format(
                ','.join(list(expected_columns - set(columns)))))
            return []
        column_indexes = {
            c: (
                header_line.find(c),
                header_line.find(columns[i + 1]) if i + 1 < len(columns) else None)
            for i, c in enumerate(columns)}
        log.debug('column_indexes : {}'.format(column_indexes))

        now = int(time.time())
        log.debug('***now: {}'.format(now))
        log.debug('***now: {}'.format(type(now)))

        rm = []
        containers_maps = []
        log.debug('Containers listed: {}'.format(len(container_lines)))
        # container_lines = container_lines[:5]
        log.debug('Containers listed: {}'.format(len(container_lines)))
        log.debug('current_containers 1: {}'.format(len(current_containers)))
        '''

        # Model the containers
        now = int(time.time())
        time_expiry = now - int(dockerPersistDuration * 3600)
        rm = []
        containers_maps = []

        # current_instances = [c.component for c in config.datasources]
        remaining_instances = list(current_containers.keys())
        log.debug('--- Remaining instances: {}'.format(remaining_instances))

        # Model the containers detected with "docker ps"
        '''
        for container in container_lines:
            c_data = {column: container[start:end].strip() for column, (start, end) in column_indexes.items()}
            container_id = c_data["CONTAINER ID"]
            instance_id = self.prepId('container_{}'.format(container_id))
            current_containers.pop(instance_id, None)

            c_instance = ObjectMap()
            c_instance.id = instance_id
            c_instance.container_id = container_id
            c_instance.title = c_data["NAMES"]
            # created, restarting, running, removing, paused, exited, or dead
            # status = c_data["STATUS"].split(' ')[0].upper()
            c_instance.container_status = c_data["STATUS"].split(' ')[0].upper()
            c_instance.image = c_data["IMAGE"]
            c_instance.command = c_data["COMMAND"]
            c_instance.created = c_data["CREATED"]
            c_instance.ports = c_data["PORTS"]
            c_instance.last_seen_model = now
            log.debug('c_instance: {}'.format(c_instance))
            containers_maps.append(c_instance)
        '''
        containers_ps_data = get_docker_data(result.output, 'PS')
        log.debug('XXX containers_ps_data: {}'.format(len(containers_ps_data)))
        # log.debug('XXX containers_ps_data: {}'.format(containers_ps_data[0]))
        containers_maps.extend(model_ps_containers(containers_ps_data))
        log.debug('---Modeled {} containers with docker ps'.format(len(containers_maps)))
        # Remove found containers from remaining_instances
        # TODO
        ps_instances = ['container_{}'.format(c["CONTAINER ID"]) for c in containers_ps_data]
        # log.debug('XXX ps_instances: {}'.format(ps_instances))
        log.debug('XXX ps_instances: {}'.format(len(ps_instances)))
        remaining_instances = set(remaining_instances) - set(ps_instances)
        log.debug('--- Remaining instances: {}'.format(remaining_instances))

        # For other existing containers, check that they remain a while after they were last seen

        '''
        log.debug('seen containers: {}'.format(len(containers_maps)))
        log.debug('old containers: {}'.format(len(current_containers)))

        time_limit = now - int(dockerPersistDuration * 3600)
        keep_count = 0
        for instance_id, last_seen in current_containers.items():
            log.debug('existing container: {} - {}'.format(last_seen, instance_id))
            # TODO: If placeholder is present, delete it
            # TODO: Check that last_seen is valid
            if last_seen['model'] and last_seen['model'] > time_limit:
                c_instance = ObjectMap()
                c_instance.id = instance_id
                containers_maps.append(c_instance)
                keep_count += 1
        log.debug('keeping old containers: {}'.format(keep_count))
        log.debug('total containers: {}'.format(len(containers_maps)))
        '''
        # Check if remaining instances have expired
        containers_maps.extend(model_remaining_containers(remaining_instances, current_containers, time_expiry))
        log.debug('---Modeled {} containers in total after keeping old instances'.format(len(containers_maps)))

        # If no container is present, create a placeholder so that the datasource is running
        if len(containers_maps) == 0:
            containers_maps.append(model_placeholder_container())

        rm.append(RelationshipMap(compname='',
                                  relname='dockerContainers',
                                  modname='ZenPacks.community.Docker.DockerContainer',
                                  objmaps=containers_maps,
                                  ))
        return rm
