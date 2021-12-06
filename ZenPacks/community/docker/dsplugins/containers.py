# stdlib Imports
import logging
import re
import time

from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Utils import prepId

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from ZenPacks.community.Docker.lib.sshclient import SSHClient
from ZenPacks.community.Docker.lib.parsers import convert_from_human, get_docker_data

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
        'getContainers',
        'getContainers_lastSeen',
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
                response = yield client.run(cmd, timeout=timeout)
                results[item] = response
                # log.debug('results: {}'.format(results))
                # log.debug('results: {}'.format(results.__dict__))
            except Exception, e:
                log.error("{} docker collect error: {}".format(config.id, e))
        log.debug('results: {}'.format(results))
        returnValue(results)

    def onSuccess(self, results, config):
        log.debug('Success - results is {}'.format(results))
        data = self.new_data()
        now = int(time.time())

        ds0 = config.datasources[0]
        # containers_data = ds0.getContainers
        containers_lastseen = ds0.getContainers_lastSeen
        log.debug('containers_lastseen : {}'.format(containers_lastseen))
        try:
            dockerPersistDuration = int(ds0.zDockerPersistDuration)
        except:
            dockerPersistDuration = 24
        time_expiry = now - int(dockerPersistDuration * 3600)

        current_instances = [c.component for c in config.datasources]
        remaining_instances = list(current_instances)
        log.debug('XXX current_containers: {}'.format(len(current_instances)))
        log.debug('XXX Datasources: {}'.format((config.datasources[0].component)))
        log.debug('XXX Found data for {} current containers'.format(len(ds0.getContainers)))

        containers_maps = []
        if 'containers' in results:
            if results['containers'].exitCode == 0:
                containers_ps_data = get_docker_data(results['containers'].output, 'PS')
                # log.debug('XXX containers_ps_data: {}'.format(len(containers_ps_data)))
                # log.debug('XXX containers_ps_data: {}'.format(containers_ps_data[0]))
                containers_maps.extend(self.model_ps_containers(containers_ps_data))
                # Remove found containers from remaining_instances
                ps_instances = ['container_{}'.format(c["CONTAINER ID"]) for c in containers_ps_data]
                # log.debug('XXX ps_instances: {}'.format(ps_instances))
                # log.debug('XXX ps_instances: {}'.format(len(ps_instances)))
                remaining_instances = set(remaining_instances) - set(ps_instances)
            else:
                containers = []
                log.error('Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                    results['containers'].exitCode,
                                                                                    results['containers'].output))
        log.debug('XXX Created mapping for {} containers'.format(len(containers_maps)))
        log.debug('XXX remaining_instances: {}'.format(remaining_instances))
        log.debug('XXX remaining_instances: {}'.format(len(remaining_instances)))

        oldest_time = int(time.time())
        for i in remaining_instances:
            i_time = containers_lastseen[i]
            log.debug('XXX i_time: {}'.format(i_time))
            oldest_time = min(i_time, oldest_time)
        log.debug('XXX lastseen   : {}'.format(containers_lastseen.values()))
        log.debug('XXX oldest_time: {} ({})'.format(oldest_time, type(oldest_time)))
        log.debug('XXX time_expiry: {} ({})'.format(time_expiry, type(time_expiry)))
        log.debug('XXX now        : {} ({})'.format(now, type(now)))
        log.debug('XXX oldest_time age: {}'.format(now - oldest_time))

        # Check if remaining instances have expired
        containers_maps.extend(self.model_remaining_containers(remaining_instances, containers_lastseen, time_expiry))

        # There must be at least one placeholder instance or the collector won't run. Emptying the list is suicide
        # containers_maps = []
        log.debug('XXX Found {} containers'.format(len(containers_maps)))
        if len(containers_maps) == 0:
            log.debug('XXX Creating placeholder instance')
            c_instance = ObjectMap()
            c_instance.id = 'container_PLACEHOLDER'
            c_instance.title = 'PLACEHOLDER (Not a real container)'
            c_instance.container_status = 'EXITED'
            c_instance.last_seen_model = 0
            log.debug('c_instance: {}'.format(c_instance))
            containers_maps.append(c_instance)

        data['maps'].append(RelationshipMap(compname='',
                                            relname='dockerContainers',
                                            modname='ZenPacks.community.Docker.DockerContainer',
                                            objmaps=containers_maps,
                                            ))

        # Fill in metrics for found containers
        # Let's suppose that the containers in stats are identical to those found in the ps output
        if 'stats' in results:
            if results['stats'].exitCode == 0:
                # stats_data = get_container_stats(results['stats'].output, log)
                stats_data = get_docker_data(results['stats'].output, 'STATS')

                # log.debug('stats_data: {}'.format(stats_data))
                # stats_data = stats_data[:45]
            else:
                stats_data = []
                log.error('XXX Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                    results['stats'].exitCode,
                                                                                    results['stats'].output))

            log.debug('XXX Updating metrics for {} containers'.format(len(stats_data)))
            remaining_instances = list(current_instances)
            for container_stats in stats_data:
                log.debug('container_stats: {}'.format(container_stats))
                c_id = 'container_{}'.format(container_stats["CONTAINER ID"])
                if c_id in remaining_instances:
                    remaining_instances.remove(c_id)
                # data['values'][c_id]['stats_last_seen'] = 0
                # data['values'].update({c_id: {'stats_last_seen': 0}})
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

        # log.debug('XXX data: {}'.format(data))
        return data

    # TODO: move this method to a shared place to use in modeler
    @staticmethod
    def model_ps_containers(data):
        maps = []
        now = int(time.time())
        for container in data:
            c_instance = ObjectMap()
            container_id = container["CONTAINER ID"]
            instance_id = prepId('container_{}'.format(container_id))
            c_instance.id = instance_id
            c_instance.container_id = container_id
            c_instance.title = container["NAMES"]
            # created, restarting, running, removing, paused, exited, or dead
            c_instance.container_status = container["STATUS"].split(' ')[0].upper()
            c_instance.image = container["IMAGE"]
            c_instance.command = container["COMMAND"]
            c_instance.created = container["CREATED"]
            c_instance.ports = container["PORTS"]
            c_instance.last_seen_model = now
            # log.debug('c_instance: {}'.format(c_instance))
            maps.append(c_instance)
        return maps

    # TODO: move this method to a shared place to use in modeler
    @staticmethod
    def model_remaining_containers(remaining_instances, containers_lastseen, time_expiry):
        log.debug('XXX remaining instances: {}'.format(remaining_instances))
        log.debug('XXX containers_lastseen: {}'.format(len(containers_lastseen)))
        maps = []
        for container in remaining_instances:
            if container in containers_lastseen:
                lastseen = containers_lastseen[container]
                if lastseen > time_expiry:
                    c_instance = ObjectMap()
                    c_instance.id = container
                    maps.append(c_instance)
            else:
                log.error('Could not find when {} was last seen'.format(container))
        return maps

    @staticmethod
    def parse_container_metrics(container_stats):
        log.debug('parse_container_metrics start')
        # CONTAINER ID - NAME - CPU % - MEM USAGE / LIMIT - MEM %  - NET I/O - BLOCK I/O - PIDS
        metrics = dict()
        container_id = prepId('container_{}'.format(container_stats["CONTAINER ID"]))

        # CPU
        # stats is here the name of the class
        metrics['stats_cpu_usage_percent'] = stats.stats_single(container_stats["CPU %"])

        # MEM USAGE / LIMIT
        metrics['stats_memory_usage'], metrics['stats_memory_limit'] = stats.stats_pair(
            container_stats["MEM USAGE / LIMIT"])

        # MEM %
        metrics['stats_memory_usage_percent'] = stats.stats_single(container_stats["MEM %"])

        # NET I/O
        metrics['stats_network_inbound'], metrics['stats_network_outbound'] = stats.stats_pair(
            container_stats["NET I/O"])

        # BLOCK I / O
        metrics['stats_block_read'], metrics['stats_block_write'] = stats.stats_pair(
            container_stats["BLOCK I/O"])

        # PIDS
        metrics['stats_num_procs'] = stats.stats_single(container_stats["PIDS"])

        if stats.stats_single(container_stats["CPU %"]):
            log.debug('BBB container_stats: {}'.format(container_stats))
            log.debug('BBB memory: {}'.format(stats.stats_pair(container_stats["MEM USAGE / LIMIT"])))
            log.debug('BBB pids: {}'.format(stats.stats_single(container_stats["PIDS"])))

        return {container_id: metrics}

    # TODO: move to a library ?
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

    # TODO: move to a library ?
    @staticmethod
    def stats_single(metrics_data):
        r = re.match(r'(\d+\.?\d+).*', metrics_data)
        return float(r.group(1)) if r else 0
