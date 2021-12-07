import logging
import time

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenUtils.Utils import prepId

log = logging.getLogger('zen.DockerModeler')

# TODO: cleanup debug

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

def model_placeholder_container():
    log.debug('XXX Creating placeholder instance')
    c_instance = ObjectMap()
    c_instance.id = 'container_PLACEHOLDER'
    c_instance.title = 'PLACEHOLDER (Not a real container)'
    c_instance.container_status = 'EXITED'
    c_instance.last_seen_model = 0
    log.debug('c_instance: {}'.format(c_instance))
    return c_instance
