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

import base64
import itertools
import json
import logging

from google.appengine.api import urlfetch
from mcfw.consts import DEBUG
from typing import Dict, Tuple, Iterable, List, Union

from plugins.gipod.models import WorkAssignment, Manifestation, ElasticsearchSettings, ItemFilterType


def get_elasticsearch_config():
    # type: () -> ElasticsearchSettings
    settings = ElasticsearchSettings.create_key().get()
    if not settings:
        raise Exception('elasticsearch settings not found')
    if not settings.items_index:
        raise Exception('items_index is missing on elasticsearch settings')
    return settings


def _request(config, path, method=urlfetch.GET, payload=None, allowed_status_codes=(200, 204)):
    # type: (ElasticsearchSettings, str, int, Union[Dict, str], Tuple[int]) -> Dict
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Basic %s' % base64.b64encode('%s:%s' % (config.auth_username, config.auth_password))
    }
    if payload:
        if isinstance(payload, basestring):
            headers['Content-Type'] = 'application/x-ndjson'
        else:
            headers['Content-Type'] = 'application/json'
    data = json.dumps(payload) if isinstance(payload, dict) else payload
    url = config.base_url + path
    if DEBUG:
        if data:
            logging.debug('%s\n%s', url, data)
        else:
            logging.debug(url)
    result = urlfetch.fetch(url, data, method, headers, deadline=30)  # type: urlfetch._URLFetchResult
    if result.status_code not in allowed_status_codes:
        logging.debug(result.content)
        raise Exception('Invalid response from elasticsearch: %s' % result.status_code)
    if result.headers.get('Content-Type').startswith('application/json'):
        return json.loads(result.content)
    return result.content


def delete_doc_operations(uid):
    yield {'delete': {'_id': uid}}


def index_doc_operations(uid, doc):
    yield {'index': {'_id': uid}}
    yield doc


def execute_bulk_request(operations):
    # type: (Iterable[Dict]) -> List[Dict]
    config = get_elasticsearch_config()
    path = '/%s/_bulk' % config.items_index
    # NDJSON - one operation per line
    payload = '\n'.join([json.dumps(op) for op in operations])
    payload += '\n'
    result = _request(config, path, urlfetch.POST, payload)
    if result['errors'] is True:
        logging.debug(result)
        # throw the first error found
        for item in result['items']:
            k = item.keys()[0]
            if 'error' in item[k]:
                reason = item[k]['error']['reason']
                raise Exception(reason)
    return result['items']


def delete_index():
    config = get_elasticsearch_config()
    path = '/%s' % config.items_index
    return _request(config, path, urlfetch.DELETE)


def create_index():
    config = get_elasticsearch_config()
    request = {
        'mappings': {
            'properties': {
                'location': {
                    'type': 'geo_point'
                },
                'start_date': {
                    'type': 'date'
                },
                'end_date': {
                    'type': 'date'
                },
                'time_frames': {
                    'type': 'date_range'
                }
            }
        }
    }
    path = '/%s' % config.items_index
    return _request(config, path, urlfetch.PUT, request)


def delete_docs(uids):
    operations = itertools.chain.from_iterable([delete_doc_operations(uid) for uid in uids])
    return execute_bulk_request(operations)


def index_documents(docs):
    # type: (List[Tuple[str, Dict]]) -> List[Dict]
    operations = itertools.chain.from_iterable([index_doc_operations(uid, doc) for uid, doc in docs])
    return execute_bulk_request(operations)


def perform_search(lat, lon, distance, start, end, cursor=None, limit=10, filter_type=ItemFilterType.RANGE):
    new_cursor, result_data = _perform_search(lat, lon, distance, start, end, cursor, limit, filter_type)
    keys = get_model_keys_from_search_result_ids([hit['_id'] for hit in result_data['hits']['hits']])
    return keys, new_cursor


def get_model_keys_from_search_result_ids(ids):
    keys = set()
    for uid in ids:
        parts = uid.split('-')

        if len(parts) == 2:
            type_, gipod_id = parts
        else:
            type_, gipod_id, _ = parts

        if type_ == 'w':
            keys.add(WorkAssignment.create_key(WorkAssignment.TYPE, gipod_id))
        elif type_ == 'm':
            keys.add(Manifestation.create_key(Manifestation.TYPE, gipod_id))
    if None in keys:
        keys.remove(None)
    return keys


def _perform_search(lat, lon, distance, start, end, cursor, limit, filter_type):
    # we can only fetch up to 10000 items with from param
    start_offset = long(cursor) if cursor else 0

    if (start_offset + limit) > 10000:
        limit = 10000 - start_offset
    if limit <= 0:
        return {'cursor': None, 'ids': []}

    query = {
        'size': limit,
        'from': start_offset,
        'query': {
            'bool': {
                'must': {
                    'match_all': {}
                },
                'filter': [
                    {
                        'geo_distance': {
                            'distance': '%sm' % distance,
                            'location': {
                                'lat': lat,
                                'lon': lon
                            }
                        }
                    }
                ]
            }
        },
        'sort': [{
            '_geo_distance': {
                'location': {
                    'lat': lat,
                    'lon': lon
                },
                'order': 'asc',
                'unit': 'm'
            }
        }]
    }

    if filter_type == ItemFilterType.START_DATE:
        query['query']['bool']['filter'].append({
            'range': {
                'start_date': {
                    'gte': start,
                    'lt': end,
                    'relation': 'within'
                }
            }
        })
    else:
        tf = {
            'gte': start,
            'relation': 'intersects'
        }
        if end:
            tf['lte'] = end

        query['query']['bool']['filter'].append({
            'range': {
                'time_frames': tf
            }
        })

    config = get_elasticsearch_config()
    path = '/%s/_search' % config.items_index
    result_data = _request(config, path, urlfetch.POST, query)

    new_cursor = None
    next_offset = start_offset + len(result_data['hits']['hits'])
    if result_data['hits']['total']['relation'] in ('eq', 'gte'):
        if result_data['hits']['total']['value'] > next_offset and next_offset < 10000:
            new_cursor = u'%s' % next_offset

    return new_cursor, result_data
