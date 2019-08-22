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
import time
import urllib

from google.appengine.ext import ndb
import webapp2

from framework.plugin_loader import get_config
from framework.utils import get_epoch_from_datetime
from mcfw.rpc import serialize_complex_value
from plugins.gipod.bizz import find_items, get_workassignment_icon, \
    get_manifestation_icon, convert_to_item_tos, convert_to_item_details_tos
from plugins.gipod.bizz.elasticsearch import search_new, search_current
from plugins.gipod.models import WorkAssignment, Manifestation, Consumer
from plugins.gipod.plugin_consts import NAMESPACE
from plugins.gipod.to import GetMapItemDetailsResponseTO, GetMapItemsResponseTO


# def _make_search_results(models, extras=None):
#     items = []
#     for m in models:
#         try:
#             icon_id = icon_color = None
#             hindrance = m.data.get('hindrance') or {}
#
#             if m.TYPE == 'w':
#                 icon_id, icon_color = get_workassignment_icon(hindrance.get('important', False))
#             elif m.TYPE == 'm':
#                 icon_id, icon_color = get_manifestation_icon(m.data['eventType'])
#             else:
#                 raise Exception('Unknown type: %s', m.TYPE)
#
#             d = {
#                 'id': m.uid,
#                 'location': {
#                     'coordinates': {
#                         'lat': m.data['location']['coordinate']['coordinates'][1],
#                         'lon': m.data['location']['coordinate']['coordinates'][0],
#                     }
#                 },
#                 'icon': {
#                     'id': icon_id,
#                     'color': icon_color
#                 },
#                 'title': m.data['description']
#             }
#             d['location']['geometry'] = []
#             if  m.data['location']['geometry']['type'] == 'Polygon':
#                 coords = []
#                 for c1 in  m.data['location']['geometry']['coordinates']:
#                     for c in c1:
#                         coords.append({'lat': c[1], 'lon': c[0]})
#                 d['location']['geometry'].append({
#                     'visible': 'zoomed',
#                     'color': '#FF0000',
#                     'type': 'Polygon',
#                     'coordinates': [coords]
#                 })
#
#             elif m.data['location']['geometry']['type'] == 'MultiPolygon':
#                 multi_coords = []
#                 for l1 in m.data['location']['geometry']['coordinates']:
#                     coords = []
#                     for l2 in l1:
#                         for c in l2:
#                             coords.append({'lat': c[1], 'lon': c[0]})
#                     if coords:
#                         multi_coords.append(coords)
#
#                 d['location']['geometry'].append({
#                     'visible': 'zoomed',
#                     'color': '#FF0000',
#                     'type': 'MultiPolygon',
#                     'coordinates': multi_coords
#                 })
#
#             d['detail'] = dict(sections=[])
#             effects = hindrance.get('effects') or []
#             if effects:
#                 d['detail']['sections'].append({
#                     'title': 'Hinder',
#                     'description': '\n'.join(effects)
#                 })
#             diversions = m.data.get('diversions') or []
#             if diversions:
#                 for i, diversion in enumerate(diversions):
#                     diversions_message = []
#                     diversion_types = diversion.get('diversionTypes') or []
#                     if diversion_types:
#                         diversions_message.append('Deze omleiding is geldig voor:\n%s' % ('\n'.join(diversion_types)))
#                     diversion_streets = diversion.get('streets') or []
#                     if diversion_streets:
#                         diversions_message.append('U kan ook volgende straten volgen:\n%s' % ('\n'.join(diversion_streets)))
#                     coords = []
#                     if  diversion['geometry']['type'] == 'LineString':
#                         for c in  diversion['geometry']['coordinates']:
#                             coords.append({'lat': c[1], 'lon': c[0]})
#
#                     d['detail']['sections'].append({
#                         'title': 'Omleiding %s' % (i + 1),
#                         'description': '\n'.join(diversions_message),
#                         'geometry': {
#                             'color': '#00FF00',
#                             'type': 'LineString',
#                             'coordinates': [coords]
#                         }
#                     })
#
#             description_message = []
#             if extras and m.uid in extras:
#                 periods_message = []
#                 for p in extras[m.uid]['periods']:
#                     tmp_start_date = p['start']
#                     tmp_end_date = p['end']
#
#                     if tmp_start_date.time():
#                         tmp_start_date_str = tmp_start_date.strftime("%d/%m %H:%M")
#                     else:
#                         tmp_start_date_str = tmp_start_date.strftime("%d/%m")
#
#                     if tmp_end_date.time():
#                         tmp_end_date_str = tmp_end_date.strftime("%d/%m %H:%M")
#                     else:
#                         tmp_end_date_str = tmp_end_date.strftime("%d/%m")
#
#                     if tmp_start_date.date() == tmp_end_date.date():
#                         description_message.append('Op %s' % (tmp_start_date.strftime("%d/%m")))
#                     else:
#                         description_message.append('Van %s tot %s' % (tmp_start_date.strftime("%d/%m"), tmp_end_date.strftime("%d/%m")))
#
#                     periods_message.append('Van %s tot %s' % (tmp_start_date_str, tmp_end_date_str))
#                 if periods_message:
#                     d['detail']['sections'].append({
#                         'title': None,
#                         'description': '\n'.join(periods_message)
#                     })
#                 if description_message:
#                     if effects:
#                         description_message.append('')
#                         description_message.extend(effects)
#                     d['description'] = '\n'.join(description_message)
#
#             items.append(d)
#         except:
#             logging.debug('uid: %s', m.uid)
#             raise
#
#     return items
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

    return_ids_result(self, list(ids), new_cursor)


def _get_items_full(self, results, new_cursor, distance):
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
            'start': result.fields[1].value,
            'end': result.fields[2].value
        }

        item_dates[item_id]['periods'].append(period)

    items = []
    if keys:
        models = ndb.get_multi(keys)
        items.extend(convert_to_item_tos(models, extras=item_dates))
    else:
        items = []

    return_items_result(self, items, new_cursor, distance)


def return_ids_result(self, ids, new_cursor):
    headers = {}
    headers['Content-Type'] = 'application/json'
    headers['Accept'] = 'application/json'
    self.response.headers = headers

    logging.debug('got %s search results', len(ids))
    self.response.out.write(json.dumps({'ids': ids, 'cursor': new_cursor}))


def return_items_result(self, items, new_cursor, distance):
    headers = {}
    headers['Content-Type'] = 'application/json'
    headers['Accept'] = 'application/json'
    self.response.headers = headers

    logging.debug('got %s search results', len(items))
    result_to = GetMapItemsResponseTO(cursor=new_cursor, items=items, distance=distance)
    start_time = time.time()
    result = serialize_complex_value(result_to, GetMapItemsResponseTO, False)
    took_time = time.time() - start_time
    logging.info('debugging.return_items_result serialize_complex_value {0:.3f}s'.format(took_time))

    start_time = time.time()
    self.response.out.write(json.dumps(result))
    took_time = time.time() - start_time
    logging.info('debugging.return_items_result self.response.out.write {0:.3f}s'.format(took_time))


def _get_items(self, is_new=False):
    params = json.loads(self.request.body) if self.request.body else {}

    lat = params.get('lat')
    lng = params.get('lon')
    distance = params.get('distance')
    start = params.get('start')
    end = params.get('end', None)
    limit = params.get('limit')
    cursor = params.get('cursor', None)
    index_type = params.get('index_type', None)

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
            if is_new:
                return_ids_result(self, [], None)
            else:
                return_items_result(self, [], None, distance)
            return
    else:
        logging.debug('not all parameters where provided')
        if is_new:
            return_ids_result(self, [], None)
        else:
            return_items_result(self, [], None, distance)
        return

    if index_type and index_type == 'elasticsearch':
        if is_new:
            ids, new_cursor = search_new(lat, lng, distance, start, end, cursor=cursor, limit=limit)
            return_ids_result(self, ids, new_cursor)
        else:
            items, new_cursor = search_current(lat, lng, distance, start, end, cursor=cursor, limit=limit)
            return_items_result(self, items, new_cursor, distance)
    else:
        r = find_items(lat, lng, distance, start=start, end=end, cursor=cursor, limit=limit, is_new=is_new)
        if not r:
            logging.debug('no search results')
            if is_new:
                return_ids_result(self, [], None)
            else:
                return_items_result(self, [], None)
            return

        results, new_cursor = r
        if is_new:
            _get_items_ids(self, results, new_cursor)
        else:
            _get_items_full(self, results, new_cursor, distance)


def return_detail_result(self, items):
    headers = {}
    headers['Content-Type'] = 'application/json'
    headers['Accept'] = 'application/json'
    self.response.headers = headers

    logging.debug('got %s results', len(items))
    result_to = GetMapItemDetailsResponseTO(items=items)
    result = serialize_complex_value(result_to, GetMapItemDetailsResponseTO, False)
    self.response.out.write(json.dumps(result))


def _get_details(self):
    params = json.loads(self.request.body) if self.request.body else {}
    ids = params.get('ids')
    if not ids:
        return_detail_result(self, [])
        return
    if type(ids) is not list:
        return_detail_result(self, [])
        return

    keys = set()
    for uid in ids:
        parts = uid.split('-')
        if len(parts) != 2:
            continue
        type_, gipod_id = parts

        if type_ == 'w':
            keys.add(WorkAssignment.create_key(WorkAssignment.TYPE, gipod_id))
        elif type_ == 'm':
            keys.add(Manifestation.create_key(Manifestation.TYPE, gipod_id))

    items = []
    if keys:
        models = ndb.get_multi(keys)
        items.extend(convert_to_item_details_tos(models))
    else:
        items = []

    return_detail_result(self, items)


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

    def post(self):
        logging.debug(self.request.body)
        _get_items(self, is_new=False)


class GipodNewItemsHandler(AuthValidationHandler):

    def post(self):
        logging.debug(self.request.body)
        _get_items(self, is_new=True)


class GipodItemDetailsHandler(AuthValidationHandler):

    def post(self):
        logging.debug(self.request.body)
        _get_details(self)
