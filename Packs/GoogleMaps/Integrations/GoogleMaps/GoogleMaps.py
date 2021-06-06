from CommonServerPython import *  # noqa # pylint: disable=unused-wildcard-import
from CommonServerUserPython import *  # noqa

# Disable insecure warnings
OUTPUTS_PREFIX = 'GoogleMaps'
NO_RESULTS_MESSAGE = 'No matching places were found.'

requests.packages.urllib3.disable_warnings()  # pylint: disable=no-member


class Client(BaseClient):
    def __init__(self, api_key: str, base_url: str, proxy: bool, insecure: bool):
        """
        Client to use in the IPinfo integration. Uses BaseClient
        """
        super().__init__(base_url=base_url,
                         verify=not insecure,
                         proxy=proxy)
        self.api_key = api_key

    def google_maps_geocode(self, search_address: str, error_on_no_results: bool) -> List[CommandResults]:
        # noinspection PyTypeChecker
        response: Dict[str, Any] = self._http_request(method='GET', url_suffix='geocode/json?',
                                                      params=assign_params(address=search_address, key=self.api_key))

        status = demisto.get(response, 'status')
        if status == 'OK':
            return parse_response(response, search_address)

        elif status == 'ZERO_RESULTS':
            if error_on_no_results:
                raise DemistoException(message=NO_RESULTS_MESSAGE, res=response)

            return [CommandResults(readable_output=NO_RESULTS_MESSAGE)]

        else:
            error_message = demisto.get(response, 'error_message') or 'See raw response for details.'
            raise DemistoException(message=error_message, res=response)


def google_maps_geocode_command(client: Client, search_address: str, error_on_no_results: bool) -> List[CommandResults]:
    return client.google_maps_geocode(search_address=search_address,
                                      error_on_no_results=error_on_no_results)


def test_module(client: Client) -> str:
    """Tests GoogleMaps by geocoding the address of Demisto's (original) HQ"""
    client.google_maps_geocode('45 Rothschild, Tel Aviv', True)
    return 'ok'  # on any failure, an exception is raised


def main():
    params = demisto.params()
    args = demisto.args()
    command = demisto.command()

    proxy = demisto.get(params, 'proxy') or False
    base_url = demisto.get(params, 'base_url') or 'https://maps.googleapis.com/maps/api/'
    api_key = demisto.get(params, 'api_key.password') or ''
    insecure = demisto.get(params, 'insecure') or False
    error_on_no_results = demisto.get(params, 'error_on_no_results') or False

    demisto.debug(f'Command being called is {command}')

    try:
        client = Client(base_url=base_url, api_key=api_key, proxy=proxy, insecure=insecure)

        if command == 'test-module':
            return_results(test_module(client))

        elif command == 'google-maps-geocode':
            return_results(google_maps_geocode_command(client=client,
                                                       error_on_no_results=error_on_no_results,
                                                       **args))

        else:
            raise NotImplementedError(f"command '{command}' is not supported")

    except Exception as e:
        demisto.error(traceback.format_exc())  # prints the traceback

        error_parts = [f'Failed to execute the {command} command.',
                       'Error:',
                       str(e)]

        if isinstance(e, DemistoException):
            error_parts.extend(('Raw response:', str(e.res)))  # pylint: disable=E1101

        return_error('\n'.join(error_parts))


def parse_response(response: Dict, search_address: str) -> List[CommandResults]:
    """ Parses Google Maps API to a list of CommandResult objects """
    first_result = response['results'][0]
    coordinate_dict = first_result['geometry']['location']
    response_address = first_result['formatted_address']

    country = None
    for component in first_result['address_components']:
        if 'types' in component and 'country' in component['types']:
            country = component['long_name']
            break

    note_outputs = {**coordinate_dict, **{'SearchAddress': search_address,
                                          'Address': response_address,
                                          'Country': country}}
    # noinspection PyTypeChecker
    readable_output = tableToMarkdown(name='Geocoding Results',
                                      t=note_outputs,
                                      headers=list(note_outputs.keys()),
                                      headerTransform=pascalToSpace)

    result_note = CommandResults(outputs_prefix=OUTPUTS_PREFIX,
                                 outputs_key_field=['lat', 'lng'],
                                 outputs=note_outputs,
                                 readable_output=readable_output,
                                 entry_type=EntryType.NOTE,
                                 raw_response=response)

    result_map = CommandResults(entry_type=EntryType.MAP_ENTRY_TYPE,
                                raw_response=coordinate_dict)
    return [result_note, result_map]


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()