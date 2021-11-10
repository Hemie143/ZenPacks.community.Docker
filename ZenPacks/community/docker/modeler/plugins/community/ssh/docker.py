# stdlib Imports
import logging
import os
import re
import time

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.Zuul.interfaces import ICatalogTool

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue

from ZenPacks.community.Docker.lib.sshclient import SSHClient

log = logging.getLogger('zen.DockerPlugin')


class docker(PythonPlugin):
    """
    Doc about this plugin
    """

    requiredProperties = (
        'zCommandUsername',
        'zCommandPassword',
        'zCommandPort',
        'zCommandCommandTimeout',
        'zKeyPath',
        'zDockerPersistDuration',
        'getContainers',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    clients = {}

    commands = {
        'version': 'docker -v',
        'containers': 'sudo docker ps -a --no-trunc',
        'cgroup': 'cat /proc/self/mountinfo | grep cgroup',
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
        """Asynchronously collect data from device. Return a deferred/"""
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
        '''
        producer = sshPlugin(client, timeout)
        log.debug('producer: {}'.format(type(producer)))
        log.debug('producer: {}'.format(producer))
        '''
        results = {}
        for item, cmd in self.commands.items():
            try:
                # results = yield producer.getResults()
                response = yield client.run(cmd, timeout=timeout)
                results[item] = response
                # log.debug('results: {}'.format(results))
                # log.debug('results: {}'.format(results.__dict__))
            except Exception, e:
                log.error("{} {} docker modeler error: {}".format(device.id, self.name(), e))
        log.debug('results: {}'.format(results))
        returnValue(results)

    def process(self, device, results, log):
        # TODO: components should stay for a while, even if containers are already removed
        # TODO: cgroup check is maybe not required, if using docker stats

        log.debug('device: {}'.format(device))
        log.debug('device: {}'.format(type(device)))
        log.debug('device: {}'.format(device.__dict__))
        log.debug('device: {}'.format(dir(device)))

        current_containers = device.getContainers
        log.debug('getContainers: {}'.format(current_containers))
        log.debug('getContainers: {}'.format(type(current_containers)))

        # test = ICatalogTool(device).search
        '''
        test = None

        log.debug('device: {}'.format(test))
        log.debug('device: {}'.format(type(test)))
        '''
        # log.debug('device: {}'.format(device.getComponentTree()))

        rm = []
        log.debug('***cgroup: {}'.format('cgroup' in results))
        if 'cgroup' in results:
            log.debug('***cgroup: {}'.format(results['cgroup']))
            cgroup_path = self.model_cgroup(results['cgroup'])
            if 'containers' in results:
                try:
                    dockerPersistDuration = int(device.zDockerPersistDuration)
                except:
                    dockerPersistDuration = 24

                container_maps = self.model_containers(results['containers'], current_containers, dockerPersistDuration,
                                                       cgroup_path)
                rm.extend(container_maps)

        # log.debug('rm: {}'.format(rm))
        # rm = []
        return rm

    def model_cgroup(self, result):
        # TODO: user parser in lib
        # log.debug('cgroup result: {}'.format(result.__dict__))
        if result.exitCode > 0:
            log.error('Could not get cgroup fs (exitcode={}) - Error: {}'.format(result.exitCode, result.stderr))
            return ''
        output = result.output.strip().splitlines()
        if not output:
            log.error('Could not get cgroup fs - Result: {}'.format(result.output))
            return ''
        for line in output:
            mount_data = line.split(' ')
            if 'cgroup' in mount_data[4]:
                mount_path = mount_data[4]
                parent_index = mount_path.find('cgroup')
                return '{}cgroup'.format(mount_path[:parent_index])
        else:
            return ''

    def model_containers(self, result, current_containers, dockerPersistDuration, cgroup_path):
        # TODO: user parser in lib
        # TODO: modeler should at least create one placeholder instance, otherwise the collector won't run
        expected_columns = set([
            "CONTAINER ID",
            "IMAGE",
            "COMMAND",
            "CREATED",
            "PORTS",
            "NAMES",
            "STATUS",
        ])
        # log.debug('containers result: {}'.format(result.__dict__))
        if result.exitCode > 0:
            log.error('Could not list containers (exitcode={}) - Error: {}'.format(result.exitCode, result.stderr))
            return []
        output = result.output.strip().splitlines()
        if not output or len(output) <= 1:
            log.error('Could not list containers - Result: {}'.format(result.output))
            return []
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
        log.debug('Containers: {}'.format(len(container_lines)))
        # container_lines = container_lines[:5]
        log.debug('Containers: {}'.format(len(container_lines)))
        log.debug('current_containers 1: {}'.format(len(current_containers)))

        # Model the containers that have been detected
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
            c_instance.cgroup_path = cgroup_path
            # c_instance.last_seen = now
            containers_maps.append(c_instance)

        # For other existing containers, check that they remain a while after they were last seen
        log.debug('seen containers: {}'.format(len(containers_maps)))
        log.debug('keep containers: {}'.format(len(current_containers)))

        time_limit = now - dockerPersistDuration * 3600
        for instance_id, last_seen in current_containers.items():
            log.debug('existing container: {} - {}'.format(last_seen, instance_id))
            # TODO: Check that last_seen is valid
            if last_seen > time_limit:
                c_instance = ObjectMap()
                c_instance.id = instance_id
                containers_maps.append(c_instance)

        rm.append(RelationshipMap(compname='',
                                  relname='dockerContainers',
                                  modname='ZenPacks.community.Docker.DockerContainer',
                                  objmaps=containers_maps,
                                  ))
        return rm