"""02 Models locations using the National Weather Service API."""

# stdlib Imports
import json
import urllib

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredList
from twisted.web.client import getPage

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin


class docker(PythonPlugin):
    """NWS Stations modeler plugin."""

    relname = 'dockerContainers'
    modname = 'ZenPacks.community.Docker'

    requiredProperties = (
        'zNwsStates',
    )

    #deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred."""
        log.info("%s: collecting data***************************", device.id)

        NwsStates = getattr(device, 'zNwsStates', None)
        if not NwsStates:
            log.error(
                "%s: %s not set.",
                device.id,
                'zNwsStates')

            returnValue(None)
        requests = []
        responses = []

        for NwsState in NwsStates:
            if NwsState:
                try:
                    response = yield getPage(
                        'https://api.weather.gov/stations?state={query}'
                            .format(query=urllib.quote(NwsState)))
                    response = json.loads(response)
                    responses.append(response)
                except Exception, e:
                    log.error(
                        "%s: %s", device.id, e)
                    returnValue(None)

                requests.extend([
                    getPage(
                        'https://api.weather.gov/stations/{query}'
                            .format(query=urllib.quote(result['properties']['stationIdentifier']))
                    )
                    for result in response.get('features')
                ])
        results = yield DeferredList(requests, consumeErrors=True)
        returnValue((responses, results))

    def process(self, device, results, log):
        """Process results. Return iterable of datamaps or None."""
        rm = self.relMap()

        (generalResults, detailedRawResults) = results

        detailedResults = {}
        for result in detailedRawResults:
            result = json.loads(result[1])
            id = self.prepId(result['properties']['stationIdentifier'])
            detailedResults[id] = result['properties']
        for result in generalResults:
            for stationResult in result.get('features'):
                id = self.prepId(stationResult['properties']['stationIdentifier'])
                zoneLink = detailedResults.get(id, {}).get('forecast', '')
                countyLink = detailedResults.get(id, {}).get('county', '')

                rm.append(self.objectMap({
                    'id': id,
                    'station_id': id,
                    'title': stationResult['properties']['name'],
                    'longitude': stationResult['geometry']['coordinates'][0],
                    'latitude': stationResult['geometry']['coordinates'][1],
                    'timezone': stationResult['properties']['timeZone'],
                    'county': countyLink.split('/')[-1],
                    'nws_zone': zoneLink.split('/')[-1],
                }))

        return rm
