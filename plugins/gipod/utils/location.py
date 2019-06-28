# -*- coding: utf-8 -*-
# Copyright 2018 Mobicage NV
# NOTICE: THIS FILE HAS BEEN MODIFIED BY MOBICAGE NV IN ACCORDANCE WITH THE APACHE LICENSE VERSION 2.0
# Copyright 2018 GIG Technology NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.5@@

import json
import logging
from math import radians, cos, sin, asin, sqrt, degrees
import urllib

from google.appengine.api import urlfetch

from plugins.gipod.plugin_consts import NAMESPACE


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in km between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
#     km = 6378.1370 * c
    return km


def geo_code(address):
    from framework.plugin_loader import get_config
    config = get_config(NAMESPACE)

    logging.debug('Geo-coding:\n%s', address)
    url = 'https://maps.googleapis.com/maps/api/geocode/json?'
    address = address.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    params = urllib.urlencode(dict(address=address.encode('utf8'),
                                   sensor='false',
                                   key=config.google_maps_key))
    response = urlfetch.fetch(url + params)
    result = json.loads(response.content)
    status = result['status']
    if status == 'ZERO_RESULTS':
        raise Exception('no_results')
    elif status != 'OK':
        raise Exception(status)

    return result['results'][0]


def address_to_coordinates(address, postal_code_required=True):
    """
    Converts an address to latitude and longitude coordinates.

    Args:
        address: The address of the location.

    Returns:
        tuple(long, long, unicode, unicode, unicode): latitude, longitude, Google place id, postal code, formatted address.

    """
    result = geo_code(address)
    lat = result['geometry']['location']['lat']
    lon = result['geometry']['location']['lng']
    address_components = result['address_components']
    postal_code = None
    for a in address_components:
        if 'postal_code' in a['types']:
            postal_code = a['short_name']
    if postal_code_required and not postal_code:
        raise GeoCodeException('Could not resolve address to coordinates')
    place_id = result['place_id']
    formatted_address = result['formatted_address']
    return lat, lon, place_id, postal_code, formatted_address
