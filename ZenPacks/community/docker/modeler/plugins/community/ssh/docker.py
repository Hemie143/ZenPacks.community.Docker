# stdlib Imports
import json
import re
import os
import logging

# Zenoss Imports
import Globals
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.Zuul import getFacade
from Products.ZenUtils.Utils import unused

# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.cred.error import UnauthorizedLogin

from ZenPacks.community.Docker.lib.sshclient import SSHClient
# from ZenPacks.community.Docker.modeler.sshPlugin import sshPlugin

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

        '''
        agent = Agent(reactor)
        headers = {
                   "Accept": ['application/json'],
                   }

        try:
            url = 'http://{}:{}/{}'.format(device.id, "8080", "/")
            log.debug('SBA url: {}'.format(url))
            # response = yield agent.request('GET', url, Headers(headers))
            http_code = response.code
            log.debug('SBA http_code: {}'.format(http_code))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)
        returnValue([http_code, response_body])
        '''


    def process(self, device, results, log):

        rm = []
        log.debug('***cgroup: {}'.format('cgroup' in results))
        if 'cgroup' in results:
            log.debug('***cgroup: {}'.format(results['cgroup']))
            cgroup_path = self.model_cgroup(results['cgroup'])
            if 'containers' in results:
                container_maps = self.model_containers(results['containers'], cgroup_path)
                rm.extend(container_maps)


        '''
        for item, result in results.items():
            log.debug('***item: {}'.format(item))
            if item == 'containers':
                container_maps = self.model_containers(result)
                rm.extend(container_maps)
        '''

        log.debug('rm: {}'.format(rm))
        return rm

    def model_cgroup(self, result):
        log.debug('cgroup result: {}'.format(result.__dict__))
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


    def model_containers(self, result, cgroup_path):
        expected_columns = set([
            "CONTAINER ID",
            "IMAGE",
            "COMMAND",
            "CREATED",
            "PORTS",
            "NAMES",
        ])
        log.debug('containers result: {}'.format(result.__dict__))
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

        rm = []
        containers_maps = []
        for container in container_lines:
            c_data = {column: container[start:end].strip() for column, (start, end) in column_indexes.items()}
            c_instance = ObjectMap()
            instance_id = c_data["CONTAINER ID"]
            c_instance.id = 'container_{}'.format(instance_id)
            c_instance.container_id = instance_id
            c_instance.title = c_data["NAMES"]
            c_instance.image = c_data["IMAGE"]
            c_instance.command = c_data["COMMAND"]
            c_instance.created = c_data["CREATED"]
            c_instance.ports = c_data["PORTS"]
            c_instance.cgroup_path = cgroup_path
            containers_maps.append(c_instance)

        rm.append(RelationshipMap(compname='',
                                  relname='dockerContainers',
                                  modname='ZenPacks.community.Docker.DockerContainer',
                                  objmaps=containers_maps,
                                  ))
        return rm