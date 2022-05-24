# stdlib Imports
import logging
import re
import time

from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Utils import prepId

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from ZenPacks.community.Docker.lib.sshclient import SSHClient
from ZenPacks.community.Docker.lib.parsers import convert_from_human, get_docker_data, stats_pair, stats_single
from ZenPacks.community.Docker.lib.utils import transform_valid_regex
from ZenPacks.community.Docker.modeler.plugins.modeler import model_ps_containers, model_remaining_containers

# Twisted Imports
from twisted.internet.defer import returnValue, inlineCallbacks

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
        'getContainers_lastSeen',
        'zDockerContainerModeled',
        'zDockerContainerNotModeled',
    )

    clients = {}
    # If creation timestamp needs to be more precise, we could use the following command:
    # "docker ps --format 'table {{.ID}}\t{{.Command}}\t{{.CreatedAt}}'"
    commands = {
        'containers': 'sudo docker ps --no-trunc',
        'stats': 'sudo docker stats --no-stream --no-trunc',
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

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting docker stats collect')
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

        results = {}
        for item, cmd in self.commands.items():
            try:
                response = yield client.run(cmd, timeout=timeout)
                results[item] = response
            except Exception, e:
                log.error("{} docker collect error: {}".format(config.id, e))
        returnValue(results)

    def onSuccess(self, results, config):
        log.debug('Success - results is {}'.format(results))
        data = self.new_data()
        now = int(time.time())

        # Model the containers
        ds0 = config.datasources[0]
        containers_lastseen = ds0.getContainers_lastSeen
        try:
            dockerPersistDuration = int(ds0.zDockerPersistDuration)
        except Exception:
            dockerPersistDuration = 24
        time_expiry = now - int(dockerPersistDuration * 3600)

        current_instances = [c.component for c in config.datasources]
        remaining_instances = list(current_instances)
        log.debug('--- Current containers: {}'.format(len(current_instances)))
        log.debug('--- Found data for {} current containers'.format(len(ds0.getContainers_lastSeen)))

        containers_maps = []
        # Model the containers detected with "docker ps"
        if 'containers' in results:
            if results['containers'].exitCode == 0:
                containers_ps_data = get_docker_data(results['containers'].output, 'PS')
                model_list = transform_valid_regex(ds0.zDockerContainerModeled)
                ignore_list = transform_valid_regex(ds0.zDockerContainerNotModeled)
                containers_maps.extend(model_ps_containers(containers_ps_data, model_list, ignore_list))
                # Remove found containers from remaining_instances
                ps_instances = ['container_{}'.format(c["CONTAINER ID"]) for c in containers_ps_data]
                remaining_instances = set(remaining_instances) - set(ps_instances)
            else:
                containers = []
                log.error('Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                    results['containers'].exitCode,
                                                                                    results['containers'].output))

        log.debug('--- Modeled {} containers with docker ps'.format(len(containers_maps)))
        log.debug('--- Remaining {} instances after docker ps'.format(len(remaining_instances)))

        # Check if remaining instances have expired
        containers_maps.extend(model_remaining_containers(remaining_instances, containers_lastseen, time_expiry))
        log.debug('--- Modeled {} containers after checking old instances'.format(len(containers_maps)))

        # There must be at least one placeholder instance or the collector won't run. Emptying the list is suicide
        if len(containers_maps) == 0:
            containers_maps.append(model_placeholder_container())

        data['maps'].append(RelationshipMap(compname='',
                                            relname='dockerContainers',
                                            modname='ZenPacks.community.Docker.DockerContainer',
                                            objmaps=containers_maps,
                                            ))

        # Fill in metrics for found containers
        # Let's suppose that the containers in stats are identical to those found in the ps output
        if 'stats' in results:
            if results['stats'].exitCode == 0:
                stats_data = get_docker_data(results['stats'].output, 'STATS')

                # log.debug('stats_data: {}'.format(stats_data))
                # stats_data = stats_data[:45]
            else:
                stats_data = []
                log.error('XXX Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                        results['stats'].exitCode,
                                                                                        results['stats'].output))

            # Update metrics with docker stats
            log.debug('--- Updating metrics for {} containers'.format(len(stats_data)))
            remaining_instances = list(current_instances)
            for container_stats in stats_data:
                log.debug('container_stats: {}'.format(container_stats))
                c_id = 'container_{}'.format(container_stats["CONTAINER ID"])
                if c_id in remaining_instances:
                    remaining_instances.remove(c_id)
                values = self.parse_container_metrics(container_stats)
                data['values'].update(values)

            # Fill in with zero the remaining instances
            for instance in remaining_instances:
                data['values'][instance]['stats_cpu_usage_percent'] = 0
                data['values'][instance]['stats_cpu_usage_percent'] = 0
                data['values'][instance]['stats_memory_usage'] = 0
                data['values'][instance]['stats_memory_limit'] = 0
                data['values'][instance]['stats_memory_usage_percent'] = 0
                data['values'][instance]['stats_network_inbound'] = 0
                data['values'][instance]['stats_network_outbound'] = 0
                data['values'][instance]['stats_block_read'] = 0
                data['values'][instance]['stats_block_write'] = 0
                data['values'][instance]['stats_num_procs'] = 0

        return data

    @staticmethod
    def parse_container_metrics(container_stats):
        # CONTAINER ID - NAME - CPU % - MEM USAGE / LIMIT - MEM %  - NET I/O - BLOCK I/O - PIDS
        metrics = dict()
        container_id = prepId('container_{}'.format(container_stats["CONTAINER ID"]))
        # CPU
        # stats is here the name of the class
        metrics['stats_cpu_usage_percent'] = stats_single(container_stats["CPU %"])
        # MEM USAGE / LIMIT
        metrics['stats_memory_usage'], metrics['stats_memory_limit'] = stats_pair(
            container_stats["MEM USAGE / LIMIT"])
        # MEM %
        metrics['stats_memory_usage_percent'] = stats_single(container_stats["MEM %"])
        # NET I/O
        metrics['stats_network_inbound'], metrics['stats_network_outbound'] = stats_pair(
            container_stats["NET I/O"])
        # BLOCK I / O
        metrics['stats_block_read'], metrics['stats_block_write'] = stats_pair(
            container_stats["BLOCK I/O"])
        # PIDS
        metrics['stats_num_procs'] = stats_single(container_stats["PIDS"])

        return {container_id: metrics}
