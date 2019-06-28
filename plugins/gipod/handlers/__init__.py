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

from datetime import datetime
import json
import logging
import urllib

from google.appengine.api import urlfetch
from google.appengine.ext import ndb
import webapp2

from plugins.gipod.bizz import find_items
from plugins.gipod.models import WorkAssignment, Manifestation
from plugins.gipod.plugin_consts import NAMESPACE
from plugins.gipod.utils.location import haversine, address_to_coordinates


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

        r = find_items(lat, lng, distance, start=start_date, cursor=cursor, limit=100)
        if not r:
            logging.debug('not search results')
            self.response.out.write(json.dumps({'items': [], 'cursor': None}))
            return

        results, new_cursor = r
        workassignment_ids = set()
        manifestion_ids = set()
        for result in results:
            uid = result.fields[0].value
            type_, id_ = uid.split('-', 1)
            if type_ == 'w':
                workassignment_ids.add(long(id_))
            elif type_ == 'm':
                manifestion_ids.add(long(id_))

        items = []
        if workassignment_ids:
            models = ndb.get_multi([WorkAssignment.create_key(id_) for id_ in workassignment_ids])
            items.extend(_make_search_results('w', models))
        if manifestion_ids:
            models = ndb.get_multi([Manifestation.create_key(id_) for id_ in manifestion_ids])
            items.extend(_make_search_results('m', models))

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
        type_, id_ = uid.split('-', 1)
        if type_ == 'w':
            m = WorkAssignment.get_by_id(long(id_))
        elif type_ == 'm':
            m = Manifestation.get_by_id(long(id_))
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


def _make_search_results(type_, models, start_date=None):
    from framework.plugin_loader import get_config
    config = get_config(NAMESPACE)
    items = []
    
    min_date = None
    if start_date:
        if start_date == 'now':
            min_date = datetime.now()

    for m in models:
        if min_date:
            if type_ == 'w' and m.start_date < min_date:
                continue
            if type_ == 'm' and m.next_start_date < min_date:
                continue
        try:
            description = []
            if m.data['owner']:
                description.append('Owner: %s' % m.data['owner'])
            hindrance = m.data.get('hindrance') or {}
            icon = None

            if type_ == 'w':
                if m.data['reference']:
                    description.append('Reference: %s' % m.data['reference'])

                description.append('Start: %s' % m.data['startDateTime'])
                description.append('End: %s' % m.data['endDateTime'])

                if hindrance.get('important', False):
                    icon = 'https://api.gipod.vlaanderen.be/Icons/WorkAssignment/important_32.png'
                else:
                    icon = 'https://api.gipod.vlaanderen.be/Icons/WorkAssignment/nonimportant_32.png'

            elif type_ == 'm':
                if m.data['status']:
                    description.append('Status: %s' % m.data['status'])

                if m.data['eventType'] == '(Werf)kraan':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/(werf)kraan_32.png'
                elif m.data['eventType'] == 'Betoging':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/betoging_32.png'
                elif m.data['eventType'] == 'Container/Werfkeet':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/containerwerfkeet_32.png'
                elif m.data['eventType'] == 'Feest/Kermis':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/feestkermis_32.png'
                elif m.data['eventType'] == 'Markt':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/markt_32.png'
                elif m.data['eventType'] == 'Speelstraat':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/speelstraat_32.png'
                elif m.data['eventType'] == 'Sportwedstrijd':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/sportwedstrijd_32.png'
                elif m.data['eventType'] == 'Stelling':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/stelling_32.png'
                elif m.data['eventType'] == 'Terras':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/terras_32.png'
                elif m.data['eventType'] == 'Verhuislift':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/verhuislift_32.png'
                elif m.data['eventType'] == 'Wielerwedstrijd - gesloten criterium':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/wielerwedstrijd%20-%20gesloten%20criterium_32.png'
                elif m.data['eventType'] == 'Wielerwedstrijd - open criterium':
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/wielerwedstrijd%20-%20open%20criterium_32.png'
                else:
                    icon = 'https://api.gipod.vlaanderen.be/Icons/Manifestation/andere_32.png'

                for p in  m.data['periods']:
                    description.append('Start: %s' % p['startDateTime'])
                    description.append('End: %s' % p['endDateTime'])

            if m.data['comment']:
                description.append(m.data['comment'])
            description.extend(hindrance.get('effects') or [])

            items.append({
                'id': m.uid,
                'hash': m.uid,
                'name': m.data['description'],
                'lat': m.data['location']['coordinate']['coordinates'][1],
                'lon': m.data['location']['coordinate']['coordinates'][0],
                'description': '\n'.join(description),
                'details': '%s/plugins/gipod/test?mode=detail_map&uid=%s' % (config.base_url, m.uid),
                'icon': icon
            })
        except:
            logging.debug('uid: %s', m.uid)
            raise

    return items

# def _get_item_detail_with_distance(details):
#     base_lat = details['location']['coordinate']['coordinates'][1]
#     base_lng = details['location']['coordinate']['coordinates'][0]
#
#     if details['location']['geometry']['type'] == 'Polygon':
#         max_distance = _get_max_distance_polygon(details, base_lat, base_lng)
#     elif details['location']['geometry']['type'] == 'MultiPolygon':
#         max_distance = _get_max_distance_multipolygon(details, base_lat, base_lng)
#     else:
#         logging.error('unknown coordinates type: %s', details['location']['geometry']['type'])
#         max_distance = 100
#
#     return details, max_distance
#
#
# def _get_max_distance_multipolygon(details, base_lat, base_lng):
#     max_distance = 100
#     for c1 in details['location']['geometry']['coordinates']:
#         for c in c1:
#             for coords in c:
#                 lat = coords[1]
#                 lng = coords[0]
#
#                 distance = long(haversine(lng, lat, base_lng, base_lat) * 1000)
#                 if distance > max_distance:
#                     max_distance = distance
#
#     return max_distance
#
#
# def _get_max_distance_polygon(details, base_lat, base_lng):
#     max_distance = 100
#     for c in details['location']['geometry']['coordinates']:
#         for coords in c:
#             lat = coords[1]
#             lng = coords[0]
#
#             distance = long(haversine(lng, lat, base_lng, base_lat) * 1000)
#             if distance > max_distance:
#                 max_distance = distance
#
#     return max_distance
