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

from google.appengine.ext import ndb
import webapp2

from plugins.gipod.bizz import find_items, get_workassignment_icon, \
    get_manifestation_icon
from plugins.gipod.models import WorkAssignment, Manifestation
from plugins.gipod.plugin_consts import NAMESPACE
from plugins.gipod.utils.location import address_to_coordinates


class GipodTestHandler(webapp2.RequestHandler):

    def get(self):
        mode = self.request.get('mode')

        if mode == 'list':
            self.set_headers()
            self.test_list()
        elif mode == 'map':
            self.test_map()
        elif mode == 'detail_map':
            self.test_detail_map()
        elif mode == 'demo':
            self.test_demo()
        elif mode == 'geo':
            self.set_headers()
            self.test_geo_code()
        else:
            self.response.set_status(200)
            self.response.out.write(json.dumps({'error': 'unknown_mode', 'mode': mode}))

    def set_headers(self):
        headers = {}
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'
        self.response.headers = headers

    def test_list(self):
        lat = self.request.get('lat')
        lng = None
        distance = 0
        if lat:
            lat = float(lat)
            lng = float(self.request.get('lon'))
            distance = long(self.request.get('distance'))
        cursor = self.request.get('cursor', None)
        start_date = self.request.get('start', None)

        r = find_items(lat, lng, distance, start=start_date, cursor=cursor, limit=100, is_test=True)
        if not r:
            logging.debug('not search results')
            self.response.out.write(json.dumps({'items': [], 'cursor': None}))
            return

        results, new_cursor = r
        keys = set()
        for result in results:
            uid = result.fields[0].value
            parts = uid.split('-')

            if len(parts) == 2:
                type_, gipod_id = parts
            else:
                type_, gipod_id, _ = parts

            if type_ == 'w':
                keys.add(WorkAssignment.create_key(WorkAssignment.TYPE, gipod_id))
            elif type_ == 'm':
                keys.add(Manifestation.create_key(Manifestation.TYPE, gipod_id))

        items = []
        if keys:
            models = ndb.get_multi(keys)
            items.extend(_make_search_results_demo(models))
        else:
            items = []

        self.response.out.write(json.dumps({'services': items, 'cursor': new_cursor}))

    def test_map(self):
        from framework.handlers import render_page
        from framework.plugin_loader import get_config

        config = get_config(NAMESPACE)

        params = {
            'google_maps_key': config.google_maps_key,
        }
        page = 'common/map.html'
        render_page(self.response, page, NAMESPACE, params)

    def test_detail_map(self):
        from framework.handlers import render_page
        from framework.plugin_loader import get_config
        uid = self.request.get('uid')
        type_, gipod_id = uid.split('-', 1)
        if type_ == 'w':
            m = WorkAssignment.create_key(WorkAssignment.TYPE, gipod_id).get()
        elif type_ == 'm':
            m = Manifestation.create_key(Manifestation.TYPE, gipod_id).get()
        else:
            self.abort(404)
            return

        details = m.data

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

    def test_demo(self):
        from framework.handlers import render_page

        params = {
        }
        page = 'common/demo.html'
        render_page(self.response, page, NAMESPACE, params)

    def test_geo_code(self):
        q = self.request.get('q')
        if q:
            lat, lon, _, _, _ = address_to_coordinates('Belgie %s' % q, postal_code_required=False)
            self.response.set_status(200)
            self.response.out.write(json.dumps({'lat': lat, 'lng': lon}))


def _make_search_results_demo(models):
    from framework.plugin_loader import get_config
    config = get_config(NAMESPACE)
    items = []

    for m in models:
        try:
            description = []
            if m.data['owner']:
                description.append('Owner: %s' % m.data['owner'])
            hindrance = m.data.get('hindrance') or {}
            icon = None

            if m.TYPE == 'w':
                if m.data['reference']:
                    description.append('Reference: %s' % m.data['reference'])

                description.append('Start: %s' % m.data['startDateTime'])
                description.append('End: %s' % m.data['endDateTime'])

                icon_url_unquoted, _ = get_workassignment_icon(hindrance.get('important', False))
                icon = urllib.quote(icon_url_unquoted)
                gipodUrl = 'https://api.gipod.vlaanderen.be/ws/v1/workassignment/%s?crs=WGS84' % m.data['gipodId']

            elif m.TYPE == 'm':
                if m.data['status']:
                    description.append('Status: %s' % m.data['status'])

                for p in  m.data['periods']:
                    description.append('Start: %s' % p['startDateTime'])
                    description.append('End: %s' % p['endDateTime'])

                icon_url_unquoted, _ = get_manifestation_icon(m.data['eventType'])
                icon = urllib.quote(icon_url_unquoted)
                gipodUrl = 'https://api.gipod.vlaanderen.be/ws/v1/manifestation/%s?crs=WGS84' % m.data['gipodId']

            if m.data['comment']:
                description.append(m.data['comment'])
            description.extend(hindrance.get('effects') or [])

            d = {
                'id': m.uid,
                'hash': m.uid,
                'name': m.data['description'],
                'lat': m.data['location']['coordinate']['coordinates'][1],
                'lon': m.data['location']['coordinate']['coordinates'][0],
                'description': '\n'.join(description),
                'icon': icon,
                'links': {
                    'map': '%s/plugins/gipod/test?mode=detail_map&uid=%s' % (config.base_url, m.uid),
                    'gipod': gipodUrl
                }
            }
            items.append(d)
        except:
            logging.debug('uid: %s', m.uid)
            raise

    return items
