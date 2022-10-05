import re
import logging

log = logging.getLogger('zen.DockerParsers')


def parse_docker_output(output, expected_columns):
    # TODO (next): handle case where metrics are printed as --, should however not appear in listing active containers
    # 191ff9626d16   monorepo-docs-depgraph-FRON-STOR-3177     --        -- / --              --        --          --
    # --

    output = output.strip().splitlines()
    if not output or len(output) <= 1:
        log.warning('Could not list containers - Result: {}'.format(output))
        return []
    header_line = output[0]
    container_lines = output[1:]
    columns = re.split(r' {2,}', header_line)
    if not set(expected_columns).issubset(columns):
        log.error('Missing column(s) while parsing output: {}'.format(','.join(list(expected_columns - set(columns)))))
        return []
    column_indexes = {
        c: (
            header_line.find(c),
            header_line.find(columns[i + 1]) if i + 1 < len(columns) else None)
        for i, c in enumerate(columns)}

    result = [{column: container[start:end].strip() for column, (start, end) in column_indexes.items()} for container
              in container_lines]
    log.debug('parse_docker_output result: {}'.format(result))
    return result


def get_docker_data(output, command):
    # {'MEM USAGE / LIMIT': '188.8MiB / 15.65GiB', 'MEM %': '1.18%', 'NAME': 'cer-be1107-job1_pubsub_1',
    # 'NET I/O': '3.75MB / 1.48MB', 'CPU %': '2.10%', 'PIDS': '85',
    # 'CONTAINER ID': '3de668dcaa7b2579ab1d0f5d6e7d6995e1c05e242aa85180a17ee64836f39f19', 'BLOCK I/O': '1.49MB / 0B'}

    # TODO (next): create dict containing columns definitions for matching commands
    if command.upper() == 'PS':
        ps_columns = set([
            "CONTAINER ID",
            "IMAGE",
            "COMMAND",
            "CREATED",
            "PORTS",
            "NAMES",
        ])
        return parse_docker_output(output, ps_columns)
    elif command.upper() == 'STATS':
        stats_columns = set([
            "CONTAINER ID",
            "NAME",
            "CPU %",
            "MEM USAGE / LIMIT",
            "MEM %",
            "NET I/O",
            "BLOCK I/O",
            "PIDS",
        ])
        return parse_docker_output(output, stats_columns)
    else:
        log.error('Could not parse the output of type {}'.format(command))


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

    # kilobyte or kibibyte : https://en.wikipedia.org/wiki/Byte#Multiple-byte_units
    if 'I' in unit:
        multiplier = 1024 ** size_name[unit.replace('I', '')]
    else:
        multiplier = 1000 ** size_name[unit]
    return int(float(value) * multiplier)


def stats_pair(metrics_data):
    r = re.match(r'(\d+\.?\d*)(\w+)\s\/\s(\d+\.?\d*)(\w+)', metrics_data)
    if r:
        val1 = convert_from_human(r.group(1), r.group(2))
        val2 = convert_from_human(r.group(3), r.group(4))
    else:
        val1 = 0
        val2 = 0
    return val1, val2


def stats_single(metrics_data):
    r = re.match(r'(\d+\.?\d+).*', metrics_data)
    return float(r.group(1)) if r else 0
