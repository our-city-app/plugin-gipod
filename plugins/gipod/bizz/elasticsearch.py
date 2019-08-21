import base64
from datetime import datetime
import json
import logging

from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from plugins.gipod.models import WorkAssignment, Manifestation, \
    ElasticsearchSettings


def get_elasticsearch_config():
    settings = ElasticsearchSettings.create_key().get()
    if not settings:
        raise Exception('elasticsearch settings not found')

    return settings.base_url, settings.auth_username, settings.auth_password


def delete_index():
    base_url, es_user, es_passwd = get_elasticsearch_config()
    headers = {
        'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (es_user, es_passwd))
    }
    result = urlfetch.fetch('%s/gipod' % base_url, method=urlfetch.DELETE, headers=headers, deadline=30)
    logging.info('Deleting gipod index: %s %s', result.status_code, result.content)

    if result.status_code not in (200, 404):
        raise Exception('Failed to delete gipod index')


def create_index():
    base_url, es_user, es_passwd = get_elasticsearch_config()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (es_user, es_passwd))
    }

    request = {
        "mappings": {
            "properties": {
                "location": {
                    "type": "geo_point"
                },
                "start_date": {
                    "type": "date",
                    "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                },
                "end_date": {
                    "type": "date",
                    "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                },
                "time_frame": {
                    "type": "date_range",
                    "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                }
            }
        }
    }

    json_request = json.dumps(request)

    result = urlfetch.fetch('%s/gipod' % base_url, json_request, method=urlfetch.PUT, headers=headers, deadline=30)
    logging.info('Creating gipod index: %s %s', result.status_code, result.content)

    if result.status_code != 200:
        raise Exception('Failed to create gipod index')


def delete_docs(uids):
    for uid in uids:
        delete_doc(uid)


def delete_doc(uid):
    base_url, es_user, es_passwd = get_elasticsearch_config()
    headers = {
        'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (es_user, es_passwd))
    }
    result = urlfetch.fetch('%s/gipod/_doc/%s' % (base_url, uid), method=urlfetch.DELETE, headers=headers, deadline=30)

    if result.status_code not in (200, 404):
        logging.info('Deleting gipod index: %s %s', result.status_code, result.content)
        raise Exception('Failed to delete index %s', uid)


def index_docs(docs):
    for d in docs:
        index_doc(d['uid'], d['data'])


def index_doc(uid, data):
    base_url, es_user, es_passwd = get_elasticsearch_config()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (es_user, es_passwd))
    }

    json_request = json.dumps(data)

    result = urlfetch.fetch('%s/gipod/_doc/%s' % (base_url, uid), json_request, method=urlfetch.PUT, headers=headers, deadline=30)
    if result.status_code not in (200, 201):
        logging.info('Creating gipod index: %s %s', result.status_code, result.content)
        raise Exception('Failed to create index %s', uid)


def search_new(lat, lon, distance, start, end, cursor=None, limit=10):
    new_cursor, result_data = _search(lat, lon, distance, start, end, cursor, limit, is_new=True)

    ids = set()
    for hit in result_data['hits']['hits']:
        uid = hit['_id']
        parts = uid.split('-')

        if len(parts) == 2:
            type_, gipod_id = parts
        else:
            type_, gipod_id, _ = parts

        item_id = '%s-%s' % (type_, gipod_id)
        ids.add(item_id)

    return list(ids), new_cursor


def search_current(lat, lon, distance, start, end, cursor=None, limit=10):
    from plugins.gipod.bizz import convert_to_item_tos
    new_cursor, result_data = _search(lat, lon, distance, start, end, cursor, limit, is_new=False)
    keys = set()
    item_dates = {}

    for hit in result_data['hits']['hits']:
        uid = hit['_id']
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
            'start': datetime.strptime(hit['_source']['start_date'], "%Y-%m-%d %H:%M:%S"),
            'end': datetime.strptime(hit['_source']['end_date'], "%Y-%m-%d %H:%M:%S")
        }

        item_dates[item_id]['periods'].append(period)

    items = []
    if keys:
        models = ndb.get_multi(keys)
        items.extend(convert_to_item_tos(models, extras=item_dates))
    else:
        items = []

    return items, new_cursor


def _search(lat, lon, distance, start, end, cursor, limit, is_new=False):
    # we can only fetch up to 10000 items with from param
    start_offset = long(cursor) if cursor else 0

    if (start_offset + limit) > 10000:
        limit = 10000 - start_offset
    if limit <= 0:
        return {'cursor': None, 'ids': []}

    d = {
        "size": limit,
        "from": start_offset,
        "query": {
            "bool" : {
                "must" : {
                    "match_all" : {}
                },
                "filter" : [
                    {
                        "geo_distance" : {
                            "distance" : "%sm" % distance,
                            "location" : {
                                "lat" :lat,
                                "lon" : lon
                            }
                        }
                    }
                ]
            }
        },
        "sort" : [
            {"_geo_distance" : {
                "location" : {
                    "lat" : lat,
                    "lon" : lon
                },
                "order" : "asc",
                "unit" : "m"}
            }
        ]
    }
    if is_new:
        d['query']['bool']['filter'].append({
            "range": {
                "start_date" : {
                    "gte" : start,
                    "lt" : end,
                    "relation" : "within"
                 }
            }
        })
    else:
        if start and end:
            tf = {
                "gte" : start,
                "lte" : end,
                "relation" : "intersects"
            }
        else:
            tf = {
                "gte" : start,
                "relation" : "intersects"
            }
        d['query']['bool']['filter'].append({
            "range": {
                "time_frame" : tf
            }
        })

    base_url, es_user, es_passwd = get_elasticsearch_config()

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (es_user, es_passwd))
    }

    json_request = json.dumps(d)

    result = urlfetch.fetch('%s/gipod/_search' % base_url, json_request, method=urlfetch.POST, headers=headers, deadline=30)
    if result.status_code not in (200,):
        logging.info('Search gipod: %s %s', result.status_code, result.content)
        raise Exception('Failed to search gipod')

    result_data = json.loads(result.content)

    new_cursor = None
    next_offset = start_offset + len(result_data['hits']['hits'])
    if result_data['hits']['total']['relation'] in ('eq', 'gte'):
        if result_data['hits']['total']['value'] > next_offset and next_offset < 10000:
            new_cursor = u'%s' % next_offset

    return new_cursor, result_data
