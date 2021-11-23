# stdlib Imports
import logging
import time
import re

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin

# Twisted Imports
from twisted.internet.defer import returnValue, inlineCallbacks

from ZenPacks.community.Docker.lib.sshclient import SSHClient
from ZenPacks.community.Docker.lib.parsers import get_containers, get_container_stats, convert_from_human

# Setup logging
log = logging.getLogger('zen.Dockercontainers')

class stats(PythonDataSourcePlugin):
    proxy_attributes = (
        'zCommandUsername',
        'zCommandPassword',
        'zCommandPort',
        'zCommandCommandTimeout',
        'zKeyPath',
        'zDockerPersistDuration',
        'getContainers',
    )

    clients = {}
    commands = {
        # 'containers': 'sudo docker ps -a --no-trunc',
        # 'cgroup': 'cat /proc/self/mountinfo | grep cgroup',
        'stats': 'sudo docker stats -a --no-stream --no-trunc',
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
            cls.clients[h].connect()
        return cls.clients[h]

    @classmethod
    def config_key(cls, datasource, context):
        # TODO: Should run once per device
        log.info('In config_key {} {} {} {} {}'.format(context.device().id,
                                                       datasource.getCycleTime(context),
                                                       datasource.rrdTemplate().id,
                                                       datasource.id,
                                                       datasource.plugin_classname,
                                                       ))

        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.rrdTemplate().id,
            datasource.id,
            datasource.plugin_classname,
        )

    @staticmethod
    def stats_pair(metrics_data):
        log.debug('metrics_data: **{}**'.format(metrics_data))
        r = re.match(r'(\d+\.?\d*)(\w+)\s\/\s(\d+\.?\d*)(\w+)', metrics_data)
        log.debug('r: **{}**'.format(r))
        if r:
            val1 = convert_from_human(r.group(1), r.group(2))
            log.debug('val1: {}'.format(val1))
            # data['values'][c_id]['stats_network_inbound'] = usage
            val2 = convert_from_human(r.group(3), r.group(4))
            log.debug('val2: {}'.format(val2))
            # data['values'][c_id]['stats_network_outbound'] = limit
        else:
            val1 = 0
            val2 = 0
            # data['values'][c_id]['stats_network_inbound'] = 0
            # data['values'][c_id]['stats_network_outbound'] = 0
        return val1, val2

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting docker stats collect')
        log.debug('A' * 80)

        log.debug('config :{}'.format(config.id))
        log.debug('config :{}'.format(config.manageIp))
        log.debug('config :{}'.format(config.datasources[0].component))

        ds0 = config.datasources[0]

        options = {'hostname': str(config.manageIp),
                   'port': ds0.zCommandPort,
                   'user': ds0.zCommandUsername,
                   'password': ds0.zCommandPassword,
                   'identities': [ds0.zKeyPath],
                   'buffersize': 32768,
                   }

        timeout = ds0.zCommandCommandTimeout
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
                # results = yield producer.getResults()
                # '/usr/bin/env sudo find ${here/cgroup_path}/memory/ -printf "\n%p\n" -exec cat {} 2>/dev/null \;'
                response = yield client.run(cmd, timeout=timeout)
                results[item] = response
                # log.debug('results: {}'.format(results))
                # log.debug('results: {}'.format(results.__dict__))
            except Exception, e:
                log.error("{} docker collect error: {}".format(config.id, e))
        log.debug('results: {}'.format(results))
        returnValue(results)

        '''
        yield True
        returnValue(0)
        '''

    def onSuccess(self, results, config):
        log.debug('Success - results is {}'.format(results))
        data = self.new_data()
        now = int(time.time())

        if 'containers' in results:
            if results['containers'].exitCode == 0:
                containers = get_containers(result['containers'].output)
                log.debug('containers: {}'.format(containers))
            else:
                containers = []
                log.error('Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                    results['containers'].exitCode,
                                                                                    results['containers'].output))
        # Fill in metrics for found containers
        if 'stats' in results:
            if results['stats'].exitCode == 0:
                stats_data = get_container_stats(results['stats'].output, log)
                # log.debug('stats_data: {}'.format(stats_data))
            else:
                stats_data = []
                log.error('Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                    results['stats'].exitCode,
                                                                                    results['stats'].output))
            for container in stats_data:
                # CONTAINER ID - NAME - CPU % - MEM USAGE / LIMIT - MEM %  - NET I/O - BLOCK I/O - PIDS
                log.debug('container: {}'.format(container))
                c_id = 'container_{}'.format(container["CONTAINER ID"])
                data['values'][c_id]['stats_last_seen'] = now

                cpu_perc = container["CPU %"]
                r = re.match(r'(\d+\.\d+).*', cpu_perc)
                if r:
                    value = float(r.group(1))
                log.debug('cpu_perc: {}'.format(value))
                data['values'][c_id]['stats_cpu_usage_percent'] = value

                mem_metrics = container["MEM USAGE / LIMIT"]
                log.debug('mem_metrics: **{}**'.format(mem_metrics))
                r = re.match(r'(\d+\.?\d*)(\w+)\s\/\s(\d+\.?\d*)(\w+)', mem_metrics)
                log.debug('r: **{}**'.format(r))
                if r:
                    usage = convert_from_human(r.group(1), r.group(2))
                    log.debug('usage: {}'.format(usage))
                    data['values'][c_id]['stats_memory_usage'] = usage
                    limit = convert_from_human(r.group(3), r.group(4))
                    log.debug('limit: {}'.format(limit))
                    data['values'][c_id]['stats_memory_limit'] = limit
                else:
                    data['values'][c_id]['stats_memory_limit'] = 0
                    data['values'][c_id]['stats_memory_usage'] = 0

                mem_perc = container["MEM %"]
                r = re.match(r'(\d+\.\d+).*', mem_perc)
                if r:
                    value = float(r.group(1))
                log.debug('mem_perc: {}'.format(value))
                data['values'][c_id]['stats_memory_usage_percent'] = value

                metric1, metric2 = self.stats_pair(container["NET I/O"])
                data['values'][c_id]['stats_network_inbound'] = metric1
                data['values'][c_id]['stats_network_outbound'] = metric2


        # Build full maps for new containers

        # Check containers that have expired

        # Fill in metrics for remaining containers (not listed but not expired yet)


        return data

