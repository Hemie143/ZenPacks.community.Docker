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
        'zDockerContainerModeled',
        'regex',
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
        dockerContainerModeled = ds0.zDockerContainerModeled

        for ds in config.datasources:
            log.debug('ds: {}'.format(ds.__dict__))
            log.debug('ds: {}'.format(ds.component))


        log.debug('zDockerContainerModeled: {}'.format(dockerContainerModeled))
        model_list = transform_valid_regex(dockerContainerModeled)
        log.debug('model_list: {}'.format(model_list))


        # Let's suppose that the containers in stats are identical to those found in the ps output
        if 'stats' in results:
            if results['stats'].exitCode == 0:
                stats_data = get_docker_data(results['stats'].output, 'STATS')

                log.debug('stats_data: {}'.format(stats_data))
                # stats_data = stats_data[:45]
            else:
                stats_data = []
                log.error('Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                    results['stats'].exitCode,
                                                                                    results['stats'].output))
            # [{'MEM USAGE / LIMIT': '207.6MiB / 19.59GiB', 'MEM %': '1.03%', 'NAME': 'practical_snyder', 'NET I/O': '7.54kB / 2.09kB', 'CPU %': '119.56%', 'PIDS': '27', 'CONTAINER ID': 'e757a32379bb1b6c5bf49c6df203af5ac02a0a2cca6c51877144147fd46e3bbb', 'BLOCK I/O': '0B / 4.33MB'}, {'MEM USAGE / LIMIT': '1.803GiB / 19.59GiB', 'MEM %': '9.20%', 'NAME': 'monorepo-build-FRON-FFM6291-BF-4-1664805967', 'NET I/O': '20.4kB / 6.47kB', 'CPU %': '149.99%', 'PIDS': '45', 'CONTAINER ID': 'e5475b2e819a05f118878ae55c1a2da8b54c3eaedb8580f2938d7b08bf637ef0', 'BLOCK I/O': '106kB / 0B'}]
            # [{'MEM USAGE / LIMIT': '1.129GiB / 19.59GiB', 'MEM %': '5.76%', 'NAME': 'wizardly_franklin', 'NET I/O': '656B / 0B', 'CPU %': '493.05%', 'PIDS': '46', 'CONTAINER ID': '1a6c6fee5a9c66d4da118dce7fd12f85fd2f05a39aa8a3db92e0bc442a68a8a5', 'BLOCK I/O': '108MB / 24.6kB'}, {'MEM USAGE / LIMIT': '2.729GiB / 19.59GiB', 'MEM %': '13.93%', 'NAME': 'monorepo-test-FRON-FFM-TES2-6218-1664807474', 'NET I/O': '80.2MB / 6.87MB', 'CPU %': '103.48%', 'PIDS': '43', 'CONTAINER ID': 'f107b2b852e5b327a8abc35e6fcb6498b052782ce14252665cbbeabdd6251897', 'BLOCK I/O': '489MB / 192GB'}]
            stats_data = [{'MEM USAGE / LIMIT': '1.129GiB / 19.59GiB', 'MEM %': '5.76%', 'NAME': 'wizardly_franklin', 'NET I/O': '656B / 0B', 'CPU %': '493.05%', 'PIDS': '46', 'CONTAINER ID': '1a6c6fee5a9c66d4da118dce7fd12f85fd2f05a39aa8a3db92e0bc442a68a8a5', 'BLOCK I/O': '108MB / 24.6kB'}, {'MEM USAGE / LIMIT': '2.729GiB / 19.59GiB', 'MEM %': '13.93%', 'NAME': 'monorepo-test-FRON-FFM-TES2-6218-1664807474', 'NET I/O': '80.2MB / 6.87MB', 'CPU %': '103.48%', 'PIDS': '43', 'CONTAINER ID': 'f107b2b852e5b327a8abc35e6fcb6498b052782ce14252665cbbeabdd6251897', 'BLOCK I/O': '489MB / 192GB'}]
            # Update metrics with docker stats
            log.debug('--- Updating metrics for {} container(s)'.format(len(stats_data)))

            # Parse the named containers
            for ds in config.datasources:
                log.debug('model_list regex: {}'.format(ds.regex))
                if not ds.regex:
                    continue
                ds_metrics = self.init_metrics()
                for container_stats in stats_data:
                    container_name = container_stats['NAME']
                    log.debug('container_name: {}'.format(container_name))
                    r = re.match(ds.regex, container_name)
                    log.debug('r: {}'.format(r))
                    if r:
                        temp = self.parse_container_metrics(container_stats)
                        log.debug('temp: {}'.format(temp))
                        ds_metrics = self.sum_metrics(ds_metrics, temp)
                log.debug('ds_metrics: {}'.format(ds_metrics))
                for k, v in ds_metrics.items():
                    data['values'][ds.component][k] = v

            # Parse the other containers and make a total
            log.debug('---------------------------Processing others and total')
            others_metrics = self.init_metrics()
            total_metrics = self.init_metrics()
            for container_stats in stats_data:
                # log.debug('container_stats: {}'.format(container_stats))
                container_name = container_stats['NAME']
                log.debug('*******************container_name: {}'.format(container_name))
                container_metrics = self.parse_container_metrics(container_stats)
                log.debug('c_metrics: {}'.format(container_metrics))
                total_metrics = self.sum_metrics(total_metrics, container_metrics)
                container_named = False
                # TODO: replace following with list comp ?
                for ds in config.datasources:
                    if not ds.regex:
                        continue
                    log.debug('ds.regex: {}'.format(ds.regex))
                    r = re.match(ds.regex, container_name)
                    log.debug('r: {}'.format(r))
                    # TODO: stupid code
                    if r:
                        container_named = True
                        break
                if not container_named:
                    others_metrics = self.sum_metrics(others_metrics, container_metrics)
                log.debug('****other_metrics: {}'.format(others_metrics))
                log.debug('****total_metrics: {}'.format(total_metrics))

            log.debug('----other_metrics: {}'.format(others_metrics))
            log.debug('----total_metrics: {}'.format(total_metrics))
            for k, v in others_metrics.items():
                data['values']['container_others'][k] = v
            for k, v in total_metrics.items():
                data['values']['container_total'][k] = v

            log.debug('----data: {}'.format(data))

            '''
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
            '''
        return data

    @staticmethod
    def sum_metrics(metrics1, metrics2):
        # TODO: Use a dict comprehension ?
        # CONTAINER ID - NAME - CPU % - MEM USAGE / LIMIT - MEM %  - NET I/O - BLOCK I/O - PIDS
        metrics = dict()
        metrics_dps = [
            'stats_cpuusagepercent',
            'stats_memoryusage',
            'stats_memorylimit',
            'stats_memoryusagepercent',
            'stats_networkinbound',
            'stats_networkoutbound',
            'stats_blockread',
            'stats_blockwrite',
            'stats_numprocs',
            'stats_numcontainers',
        ]
        for m in metrics_dps:
            metrics[m] = metrics1[m] + metrics2[m]
        return metrics

    @staticmethod
    def parse_container_metrics(container_stats):
        # CONTAINER ID - NAME - CPU % - MEM USAGE / LIMIT - MEM %  - NET I/O - BLOCK I/O - PIDS
        metrics = dict()
        # CPU
        # stats is here the name of the class
        metrics['stats_cpuusagepercent'] = stats_single(container_stats["CPU %"])
        # MEM USAGE / LIMIT
        metrics['stats_memoryusage'], metrics['stats_memorylimit'] = stats_pair(
            container_stats["MEM USAGE / LIMIT"])
        # MEM %
        metrics['stats_memoryusagepercent'] = stats_single(container_stats["MEM %"])
        # NET I/O
        metrics['stats_networkinbound'], metrics['stats_networkoutbound'] = stats_pair(
            container_stats["NET I/O"])
        # BLOCK I / O
        metrics['stats_blockread'], metrics['stats_blockwrite'] = stats_pair(
            container_stats["BLOCK I/O"])
        # PIDS
        metrics['stats_numprocs'] = stats_single(container_stats["PIDS"])
        metrics['stats_numcontainers'] = 1
        return metrics


    @staticmethod
    def init_metrics():
        metrics = {
            "stats_cpuusagepercent": 0,
            "stats_memoryusage": 0,
            "stats_memorylimit": 0,
            "stats_memoryusagepercent": 0,
            "stats_networkinbound": 0,
            "stats_networkoutbound": 0,
            "stats_blockread": 0,
            "stats_blockwrite": 0,
            "stats_numprocs": 0,
            "stats_numcontainers": 0,
        }
        return metrics