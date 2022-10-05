# stdlib Imports
import logging
import re

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from ZenPacks.community.Docker.lib.sshclient import SSHClient
from ZenPacks.community.Docker.lib.parsers import get_docker_data, stats_pair, stats_single

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
        # 'containers': 'sudo docker ps --no-trunc',
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

        # Use the docker stats output
        if 'stats' in results:
            if results['stats'].exitCode == 0:
                stats_data = get_docker_data(results['stats'].output, 'STATS')
            else:
                stats_data = []
                log.error('Could not collect containers on {}: (code:{}) {}'.format(config.id,
                                                                                    results['stats'].exitCode,
                                                                                    results['stats'].output))
            # [{'MEM USAGE / LIMIT': '1.129GiB / 19.59GiB', 'MEM %': '5.76%', 'NAME': 'wizardly_franklin',
            # 'NET I/O': '656B / 0B', 'CPU %': '493.05%', 'PIDS': '46',
            # 'CONTAINER ID': '1a6c6fee5a9c66d4da118dce7fd12f85fd2f05a39aa8a3db92e0bc442a68a8a5',
            # 'BLOCK I/O': '108MB / 24.6kB'}, {'MEM USAGE / LIMIT': '2.729GiB / 19.59GiB', 'MEM %': '13.93%',
            # 'NAME': 'monorepo-test-FRON-FFM-TES2-6218-1664807474', 'NET I/O': '80.2MB / 6.87MB', 'CPU %': '103.48%',
            # 'PIDS': '43', 'CONTAINER ID': 'f107b2b852e5b327a8abc35e6fcb6498b052782ce14252665cbbeabdd6251897',
            # 'BLOCK I/O': '489MB / 192GB'}]

            # Parse the named containers
            for ds in config.datasources:
                if not ds.regex:
                    continue
                ds_metrics = self.init_metrics()
                for container_stats in stats_data:
                    container_name = container_stats['NAME']
                    if re.match(ds.regex, container_name):
                        ds_metrics = self.sum_metrics(ds_metrics, self.parse_container_metrics(container_stats))
                for k, v in ds_metrics.items():
                    data['values'][ds.component][k] = v

            # Parse the other containers and make a total
            others_metrics = self.init_metrics()
            total_metrics = self.init_metrics()
            for container_stats in stats_data:
                container_name = container_stats['NAME']
                container_metrics = self.parse_container_metrics(container_stats)
                total_metrics = self.sum_metrics(total_metrics, container_metrics)
                if not any([re.match(ds.regex, container_name) for ds in config.datasources if ds.regex]):
                    others_metrics = self.sum_metrics(others_metrics, container_metrics)
            for k, v in others_metrics.items():
                data['values']['container_others'][k] = v
            for k, v in total_metrics.items():
                data['values']['container_total'][k] = v
        return data

    @staticmethod
    def sum_metrics(metrics1, metrics2):
        # CONTAINER ID - NAME - CPU % - MEM USAGE / LIMIT - MEM %  - NET I/O - BLOCK I/O - PIDS
        return {k: metrics1[k] + metrics2[k] for k in metrics1.keys()}

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
