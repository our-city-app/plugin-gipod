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

from google.appengine.ext import ndb
import webapp2

from framework.utils import get_epoch_from_datetime
from plugins.gipod.bizz import find_items, get_workassignment_icon, \
    get_manifestation_icon
from plugins.gipod.models import WorkAssignment, Manifestation, Consumer


def _make_search_results(models, extras=None):
    items = []
    for m in models:
        try:
            hindrance = m.data.get('hindrance') or {}
            icon_url, icon_color = None

            if m.TYPE == 'w':
                icon_url, icon_color = get_workassignment_icon(hindrance.get('important', False))
            elif m.TYPE == 'm':
                icon_url, icon_color = get_manifestation_icon(m.data['eventType'])

            d = {
                'id': m.uid,
                'location': {
                    'coordinates': {
                        'lat': m.data['location']['coordinate']['coordinates'][1],
                        'lon': m.data['location']['coordinate']['coordinates'][0],
                    }
                },
                'icon': {
                    'icon': icon_url,
                    'color': icon_color
                },
                'title': m.data['description']
            }
            d['location']['geometry'] = []
            if  m.data['location']['geometry']['type'] == 'Polygon':
                coords = []
                for c1 in  m.data['location']['geometry']['coordinates']:
                    for c in c1:
                        coords.append({'lat': c[1], 'lon': c[0]})
                d['location']['geometry'].append({
                    'visible': 'zoomed',
                    'color': '#FF0000',
                    'type': 'Polygon',
                    'coordinates': [coords]
                })

            elif  m.data['location']['geometry']['type'] == 'MultiPolygon':
                multi_coords = []
                for l1 in m.data['location']['geometry']['coordinates']:
                    coords = []
                    for l2 in l1:
                        for c in l2:
                            coords.append({'lat': c[1], 'lon': c[0]})
                    if coords:
                        multi_coords.append(coords)

                d['location']['geometry'].append({
                    'visible': 'zoomed',
                    'color': '#FF0000',
                    'type': 'MultiPolygon',
                    'coordinates': multi_coords
                })

            d['detail'] = dict(sections=[])
            effects = hindrance.get('effects') or []
            if effects:
                d['detail']['sections'].append({
                    'title': 'Hinderance',
                    'description': '\n'.join(effects)
                })
            diversions = m.data.get('diversions') or []
            if diversions:
                for i, diversion in enumerate(diversions):
                    diversions_message = []
                    diversion_types = diversion.get('diversionTypes') or []
                    if diversion_types:
                        diversions_message.append('This diversion is valid for:\n%s' % ('\n'.join(diversion_types)))
                    diversion_streets = diversion.get('streets') or []
                    if diversion_streets:
                        diversions_message.append('You can also follow the following streets:\n%s' % ('\n'.join(diversion_streets)))
                    coords = []
                    if  diversion['geometry']['type'] == 'LineString':
                        for c in  diversion['geometry']['coordinates']:
                            coords.append({'lat': c[1], 'lon': c[0]})

                    d['detail']['sections'].append({
                        'title': 'Diversion %s' % (i + 1),
                        'description': '\n'.join(diversions_message),
                        'geometry': {
                            'color': '#00FF00',
                            'type': 'LineString',
                            'coordinates': [coords]
                        }
                    })

            if extras and m.uid in extras:
                periods_message = []
                for p in extras[m.uid]['periods']:
                    tmp_start_date = datetime.utcfromtimestamp(p['start'])
                    tmp_end_date = datetime.utcfromtimestamp(p['end'])

                    if tmp_start_date.time():
                        tmp_start_date_str = tmp_start_date.strftime("%d/%m %H:%M")
                    else:
                        tmp_start_date_str = tmp_start_date.strftime("%d/%m")

                    if tmp_end_date.time():
                        tmp_end_date_str = tmp_end_date.strftime("%d/%m %H:%M")
                    else:
                        tmp_end_date_str = tmp_end_date.strftime("%d/%m")

                    periods_message.append('Van %s tot %s' % (tmp_start_date_str, tmp_end_date_str))
                if periods_message:
                    d['detail']['sections'].append({
                        'title': 'Periods',
                        'description': '\n'.join(periods_message)
                    })

            items.append(d)
        except:
            logging.debug('uid: %s', m.uid)
            raise

    return items


def _get_items_ids(self, results, new_cursor):
    ids = set()
    for result in results:
        uid = result.fields[0].value
        parts = uid.split('-')

        if len(parts) == 2:
            type_, gipod_id = parts
        else:
            type_, gipod_id, _ = parts

        item_id = '%s-%s' % (type_, gipod_id)
        ids.add(item_id)

    logging.debug('got %s search results', len(ids))
    self.response.out.write(json.dumps({'ids': list(ids), 'cursor': new_cursor}))


def _get_items_full(self, results, new_cursor):
    keys = set()
    item_dates = {}
    for result in results:
        uid = result.fields[0].value
        parts = uid.split('-')

        if len(parts) == 2:
            type_, gipod_id = parts
        else:
            type_, gipod_id, _ = parts

        item_id = '%s-%s' % (type_, gipod_id)
        if type_ == 'w':
            keys.add(WorkAssignment.create_key(WorkAssignment.TYPE, gipod_id))
        elif type_ == 'm':
            keys.add(Manifestation.create_key(Manifestation.TYPE, gipod_id))

        if item_id not in item_dates:
            item_dates[item_id] = {'periods': []}

        period = {
            'start': get_epoch_from_datetime(result.fields[1].value),
            'end': get_epoch_from_datetime(result.fields[2].value)
        }

        item_dates[item_id]['periods'].append(period)

    items = []
    if keys:
        models = ndb.get_multi(keys)
        items.extend(_make_search_results(models, extras=item_dates))
    else:
        items = []

    logging.debug('got %s search results', len(items))
    self.response.out.write(json.dumps({'items': items, 'cursor': new_cursor}))


def _get_items(self, is_new=False):
    headers = {}
    headers['Content-Type'] = 'application/json'
    headers['Accept'] = 'application/json'
    self.response.headers = headers

    lat = self.request.get('lat')
    lng = self.request.get('lon')
    distance = self.request.get('distance')
    start = self.request.get('start')
    end = self.request.get('end', None)
    limit = self.request.get('limit')
    cursor = self.request.get('cursor', None)

    if lat and lng and distance and start and limit:
        try:
            lat = float(lat)
            lng = float(lng)
            distance = long(distance)
            limit = long(limit)
            if limit > 1000:
                limit = 1000
        except:
            logging.debug('not all parameters where provided correctly', exc_info=True)
            self.response.out.write(json.dumps({'items': [], 'cursor': None}))
            return
    else:
        logging.debug('not all parameters where provided')
        self.response.out.write(json.dumps({'items': [], 'cursor': None}))
        return

    r = find_items(lat, lng, distance, start=start, end=end, cursor=cursor, limit=limit, is_new=is_new)
    if not r:
        logging.debug('no search results')
        self.response.out.write(json.dumps({'items': [], 'cursor': None}))
        return

    results, new_cursor = r
    if is_new:
        _get_items_ids(self, results, new_cursor)
    else:
        _get_items_full(self, results, new_cursor)


class AuthValidationHandler(webapp2.RequestHandler):

    def dispatch(self):
        consumer_key = self.request.headers.get('consumer_key', None)
        if not consumer_key:
            self.abort(401)
            return
        c = Consumer.create_key(consumer_key).get()
        if not c:
            self.abort(401)
            return

        return super(AuthValidationHandler, self).dispatch()


class GipodItemsHandler(AuthValidationHandler):

    def get(self):
        _get_items(self, is_new=False)


class GipodNewItemsHandler(AuthValidationHandler):

    def get(self):
        _get_items(self, is_new=True)
