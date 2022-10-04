import logging
import re
import time

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenUtils.Utils import prepId

log = logging.getLogger('zen.DockerModeler')


def check_containers_modeled(model_list, title):
    # Return True if container is to be modeled or if model_list is empty
    log.debug('check_containers_modeled: {}'.format(bool(model_list == [])))
    if model_list and len(model_list) > 0:
        for name in model_list:
            # TODO: Check if name is empty ? Check that this is a valid regex ?
            if re.match(name, title):
                return True
        return False
    else:
        return False


def model_ps_containers(data, model_list):
    maps = []
    now = int(time.time())
    for container in data:
        title = container["NAMES"]
        model_enable = check_containers_modeled(model_list, title)
        log.debug('model_enable: {}={}'.format(title, model_enable))
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

def generate_container_others():
    c_instance = ObjectMap()
    title = '_Other Containers'
    instance_id = prepId('container_others')
    c_instance.id = instance_id
    c_instance.title = title
    return c_instance

def generate_container_total():
    c_instance = ObjectMap()
    title = '_Total of all Containers'
    instance_id = prepId('container_total')
    c_instance.id = instance_id
    c_instance.title = title
    return c_instance