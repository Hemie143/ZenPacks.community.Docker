import re
import math

def get_cgroup_path(output):
    output = output.strip().splitlines()
    if not output:
        # log.error('Could not get cgroup fs - Result: {}'.format(result.output))
        return ''
    for line in output:
        mount_data = line.split(' ')
        if 'cgroup' in mount_data[4]:
            mount_path = mount_data[4]
            parent_index = mount_path.find('cgroup')
            return '{}cgroup'.format(mount_path[:parent_index])
    else:
        return ''

# TODO: replace two next functions with one single function
def get_containers(output):
    # TODO: Add logging
    expected_columns = set([
        "CONTAINER ID",
        "IMAGE",
        "COMMAND",
        "CREATED",
        "PORTS",
        "NAMES",
    ])

    output = output.strip().splitlines()
    if not output or len(output) <= 1:
        # log.error('Could not list containers - Result: {}'.format(result.output))
        return []
    header_line = output[0]
    container_lines = output[1:]
    columns = re.split(r' {2,}', header_line)
    # log.debug('columns : {}'.format(columns))
    if not set(expected_columns).issubset((columns)):
        '''
        log.error('Missing column(s) while listing containers: {}'.format(
            ','.join(list(expected_columns - set(columns)))))
        '''
        return []
    column_indexes = {
        c: (
            header_line.find(c),
            header_line.find(columns[i + 1]) if i + 1 < len(columns) else None)
        for i, c in enumerate(columns)}
    # log.debug('column_indexes : {}'.format(column_indexes))

    # TODO: List comprehension
    result = []
    for container in container_lines:
        result.append({column: container[start:end].strip() for column, (start, end) in column_indexes.items()})
    return result

def get_container_stats(output, log):
    expected_columns = set([
        "CONTAINER ID",
        "NAME",
        "CPU %",
        "MEM USAGE / LIMIT",
        "MEM %",
        "NET I/O",
        "BLOCK I/O",
        "PIDS",
    ])
    output = output.strip().splitlines()
    if not output or len(output) <= 1:
        log.error('Could not list containers - Result: {}'.format(result.output))
        return []
    header_line = output[0]
    container_lines = output[1:]
    columns = re.split(r' {2,}', header_line)
    log.debug('columns : {}'.format(columns))
    if not set(expected_columns).issubset((columns)):
        log.error('Missing column(s) while parsing output: {}'.format(','.join(list(expected_columns - set(columns)))))
        return []
    column_indexes = {
        c: (
            header_line.find(c),
            header_line.find(columns[i + 1]) if i + 1 < len(columns) else None)
        for i, c in enumerate(columns)}
    log.debug('column_indexes : {}'.format(column_indexes))

    # TODO: List comprehension
    result = []
    for container in container_lines:
        result.append({column: container[start:end].strip() for column, (start, end) in column_indexes.items()})
    return result


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

def convert_from_human(value, unit):
    if float(value) == 0.0:
        return 0.0

    unit = unit.upper()
    size_name = {
        "B": 0,
        "KB": 1,
        "MB": 2,
        "GB": 3,
        "TB": 4,
        "PB": 5,
        "EB": 6,
        "ZB": 7,
        "YB": 8,
        }

    if 'I' in unit:
        multiplier = 1024 ** size_name[unit.replace('I', '')]
    else:
        multiplier = 1000 ** size_name[unit]
    return (int(float(value)) * multiplier)

