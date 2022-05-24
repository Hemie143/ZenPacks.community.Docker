import logging
import re

log = logging.getLogger('zen.DockerLibUtils')

def transform_valid_regex(regex_list):
    result = []
    for item in regex_list:
        try:
            re.compile(item)
            result.append(item)
        except:
            log.warn('Ignoring "{}" in regex_list. '
                     'Invalid Regular Expression.'.format(item))
    return result
