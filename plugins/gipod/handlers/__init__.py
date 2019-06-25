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
import urllib

from google.appengine.api import urlfetch
import webapp2

from plugins.gipod.plugin_consts import NAMESPACE
from plugins.gipod.utils import haversine

class GipodTestHandler(webapp2.RequestHandler):
    def get(self):
        mode = self.request.get('mode', 'test')

        if mode == 'count':
            self.set_headers()
            self.test_count_()
        elif mode == 'location':
            self.set_headers()
            self.test_location()
        elif mode == 'work':
            self.set_headers()
            self.test_work_detail()
        elif mode == 'map':
            self.test_map()
        else:
            self.response.set_status(200)
            self.response.out.write(json.dumps({'ok': 'bajaat'}))

    def set_headers(self):
        headers = {}
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'
        self.response.headers = headers

    def test_count(self):
        url = 'https://api.gipod.vlaanderen.be/ws/v1/manifestation'
        offset = 0
        params = {}
        params['enddate'] = '2020-01-01'
        params['limit'] = '1000'
        while True:
            params['offset'] = '%s' % offset
            size = len(_do_request(url, params))
            if size == 0:
                break
            offset += size

        self.response.out.write(json.dumps({'count': offset}))

    def test_location(self):
        url = 'https://api.gipod.vlaanderen.be/ws/v1/workassignment'
        params = {}
        params['city'] = 'Lille'
        params['enddate'] = '2020-01-01'
        params['limit'] = '10'
        items = _do_request(url, params)
        
        l = []
        for item in items:
            d = {}
            d['detail_url'] = 'https://api.gipod.vlaanderen.be/ws/v1/workassignment/%s' % item['gipodId']
            d['map_url'] = 'http://localhost:8800/plugins/gipod/test?mode=map&id=%s' % item['gipodId']

            details, max_distance = _get_item_detail_with_distance(d['detail_url'])
            d['type'] = details['location']['geometry']['type']
            d['max_distance'] = max_distance

            l.append(d)

        self.response.out.write(json.dumps({'items': l}))

    def test_work_detail(self):
        url = 'https://api.gipod.vlaanderen.be/ws/v1/workassignment/%s' % self.request.get('id')

        details, max_distance = _get_item_detail_with_distance(url)
        
        self.response.out.write(json.dumps({'details': details, 'max_distance': max_distance}))

    def test_map(self):
        from framework.handlers import render_page
        from framework.plugin_loader import get_config
        url = 'https://api.gipod.vlaanderen.be/ws/v1/workassignment/%s' % self.request.get('id')

        details = _do_request(url, None)

        base_lat = details['location']['coordinate']['coordinates'][1]
        base_lng = details['location']['coordinate']['coordinates'][0]
        coords = []
        if details['location']['geometry']['type'] == 'Polygon':
            map_type = 'polygon'
            for c1 in details['location']['geometry']['coordinates']:
                for c in c1:
                    coords.append({'lat': c[1], 'lng': c[0]})

        elif details['location']['geometry']['type'] == 'MultiPolygon':
            map_type = 'multipolygon'
            coords = details['location']['geometry']['coordinates']
        else:
            self.abort(404)
            return

        config = get_config(NAMESPACE)

        params = {
            'google_maps_key': config.google_maps_key,
            'base_lat': base_lat,
            'base_lng': base_lng,
            'coords': coords
        }
        page = 'common/map_%s.html' % map_type
        render_page(self.response, page, NAMESPACE, params)


def _do_request(url, params=None):
    if params:
        query_params = urllib.urlencode(params)
        if query_params:
            url = '%s?%s' % (url, query_params)

    logging.info('_do_request: %s', url)

    result = urlfetch.fetch(url, deadline=30, follow_redirects=False)
    if result.status_code != 200:
        raise Exception('Failed to get gipod data')

    r = json.loads(result.content)
    return r


def _get_item_detail_with_distance(url):
    details = _do_request(url, None)

    base_lat = details['location']['coordinate']['coordinates'][1]
    base_lng = details['location']['coordinate']['coordinates'][0]
    
    logging.info('base coords: %s', details['location']['coordinate']['coordinates'])

    if details['location']['geometry']['type'] == 'Polygon':
        max_distance = _get_max_distance_polygon(details, base_lat, base_lng)
    elif details['location']['geometry']['type'] == 'MultiPolygon':
        max_distance = _get_max_distance_multipolygon(details, base_lat, base_lng)
    else:
        logging.error('unknown coordinates type: %s', details['location']['geometry']['type'])
        max_distance = 100

    return details, max_distance


def _get_max_distance_multipolygon(details, base_lat, base_lng):
    max_distance = 100
    for c1 in details['location']['geometry']['coordinates']:
        for c in c1:
            for coords in c:
                lat = coords[1]
                lng = coords[0]

                distance = long(haversine(lng, lat, base_lng, base_lat) * 1000)
                if distance > max_distance:
                    max_distance = distance

    return max_distance


def _get_max_distance_polygon(details, base_lat, base_lng):
    max_distance = 100
    for c in details['location']['geometry']['coordinates']:
        for coords in c:
            lat = coords[1]
            lng = coords[0]

            distance = long(haversine(lng, lat, base_lng, base_lat) * 1000)
            if distance > max_distance:
                max_distance = distance

    return max_distance
