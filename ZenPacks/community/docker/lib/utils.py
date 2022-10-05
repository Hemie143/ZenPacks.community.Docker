import logging
import re

log = logging.getLogger('zen.DockerLibUtils')


def transform_valid_regex(regex_list):
    result = []
    for item in regex_list:
        if len(item) == 0 or item == '.*':
            continue
        try:
            re.compile(item)
            result.append(item)
        except Exception as e:
            log.warn('Ignoring "{}" in regex_list. Exception: {}. '.format(item, e))
    return result
