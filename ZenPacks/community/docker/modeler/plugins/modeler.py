import logging
import re
import time

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenUtils.Utils import prepId

log = logging.getLogger('zen.DockerModeler')


def check_containers_modeled(model_list, ignore_list, title):
    # Return False if container is not to be modeled
    for name in ignore_list:
        if re.match(name, title):
            return False

    # Return True if container is to be modeled or if model_list is empty
    if model_list:
        for name in model_list:
            if re.match(name, title):
                return True
        return False
    else:
        return True


def model_ps_containers(data, model_list, ignore_list):
    maps = []
    now = int(time.time())
    for container in data:
        title = container["NAMES"]
        model_enable = check_containers_modeled(model_list, ignore_list, title)
        log.debug('model_enable: {}'.format(model_enable))
        if model_enable is False:
            continue
        c_instance = ObjectMap()
        container_id = container["CONTAINER ID"]
        instance_id = prepId('container_{}'.format(container_id))
        c_instance.id = instance_id
        c_instance.container_id = container_id
        c_instance.title = title
        # created, restarting, running, removing, paused, exited, or dead
        c_instance.container_status = container["STATUS"].split(' ')[0].upper()
        c_instance.image = container["IMAGE"]
        c_instance.command = container["COMMAND"]
        c_instance.created = container["CREATED"]
        c_instance.ports = container["PORTS"]
        c_instance.last_seen_model = now
        maps.append(c_instance)
    return maps


def model_remaining_containers(remaining_instances, containers_lastseen, time_expiry):
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
    c_instance = ObjectMap()
    c_instance.id = 'container_PLACEHOLDER'
    c_instance.title = 'PLACEHOLDER (Not a real container)'
    c_instance.container_status = 'EXITED'
    c_instance.last_seen_model = 0
    log.debug('c_instance: {}'.format(c_instance))
    return c_instance
