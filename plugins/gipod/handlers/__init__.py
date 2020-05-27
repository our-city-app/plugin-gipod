# -*- coding: utf-8 -*-
# Copyright 2019 Green Valley Belgium NV
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
from datetime import datetime

import webapp2
from google.appengine.ext import ndb

from framework.utils import try_or_defer
from plugins.gipod.bizz import convert_to_item_tos, convert_to_item_details_tos, \
    save_last_load_map_request
from plugins.gipod.bizz.elasticsearch import perform_search, get_model_keys_from_search_result_ids
from plugins.gipod.models import Consumer, ItemFilterType
from plugins.gipod.to import GetMapItemDetailsResponseTO, GetMapItemsResponseTO


def _get_item_ids(lat, lon, distance, start, end, cursor, limit, filter_type):
    # type: (float, float, int, str, str, str, int, str) -> tuple[list[int], str]
    keys, new_cursor = perform_search(lat, lon, distance, start, end, cursor, limit, filter_type)
    ids = [key.id() for key in keys]
    return ids, new_cursor


def _get_items(lat, lon, distance, start, end, cursor, limit, filter_type):
    keys, new_cursor = perform_search(lat, lon, distance, start, end, cursor, limit, filter_type)
    # This can take a while, because some models can have large amounts of location data
    models = ndb.get_multi(keys)
    items = convert_to_item_tos(m for m in models if m)
    return GetMapItemsResponseTO(items=items, cursor=new_cursor, distance=distance)


def _get_details(ids):
    keys = get_model_keys_from_search_result_ids(ids)
    models = ndb.get_multi(keys)
    return convert_to_item_details_tos([key.id() for key in keys], models)


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


class GipodMapHandler(AuthValidationHandler):

    def post(self):
        logging.debug(self.request.body)
        params = json.loads(self.request.body) if self.request.body else {}
        user_id = params.get('user_id')
        if user_id:
            try_or_defer(save_last_load_map_request, user_id, datetime.utcnow())


class GipodItemsHandler(AuthValidationHandler):

    def post(self):
        logging.debug(self.request.body)
        params = json.loads(self.request.body) if self.request.body else {}
        try:
            result = _get_items(*_parse_params(params))
        except Exception as e:
            logging.exception('Could not fetch items: %s', e.message)
            result = GetMapItemsResponseTO(items=[], new_cursor=None, distance=0)
        self.response.headers = {'Content-Type': 'application/json'}
        logging.debug('got %s search results', len(result.items))
        json.dump(result.to_dict(), self.response.out)


class GipodItemIdsHandler(AuthValidationHandler):

    def post(self):
        logging.debug(self.request.body)
        params = json.loads(self.request.body) if self.request.body else {}
        try:
            ids, new_cursor = _get_item_ids(*_parse_params(params))
        except Exception as e:
            logging.exception('Could not fetch new items: %s', e.message)
            ids = []
            new_cursor = None
        logging.debug('got %s search results', len(ids))
        self.response.headers = {'Content-Type': 'application/json'}
        json.dump({'ids': ids, 'cursor': new_cursor}, self.response.out)


class GipodItemDetailsHandler(AuthValidationHandler):

    def post(self):
        params = json.loads(self.request.body) if self.request.body else {}
        ids = params.get('ids', [])
        result = GetMapItemDetailsResponseTO(items=_get_details(ids))
        logging.debug('got %s results', len(result.items))
        self.response.headers = {'Content-Type': 'application/json'}
        json.dump(result.to_dict(), self.response.out)


def _parse_params(params):
    lat = params.get('lat')
    lon = params.get('lon')
    distance = params.get('distance')
    start = params.get('start')
    end = params.get('end', None)
    limit = params.get('limit')
    cursor = params.get('cursor', None)
    filter_type = params.get('filter_type', ItemFilterType.RANGE)

    if lat and lon and distance and start and limit and filter_type:
        lat = float(lat)
        lon = float(lon)
        distance = long(distance)
        limit = long(limit)
        if limit > 1000:
            limit = 1000
    else:
        raise Exception('Not all parameters were provided')
    return lat, lon, distance, start, end, cursor, limit, filter_type
