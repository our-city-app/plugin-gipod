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

from google.appengine.api import urlfetch, search

from plugins.gipod.plugin_consts import GIPOD_API_URL, SYNC_QUEUE
from plugins.gipod.utils import drop_index

LOCATION_INDEX = 'LOCATION_INDEX'


def do_request(relative_url, params=None):
    url = '%s%s' % (GIPOD_API_URL, relative_url)
    if params:
        query_params = urllib.urlencode(params)
        if query_params:
            url = '%s?%s' % (url, query_params)

    logging.info('do_request: %s', url)

    result = urlfetch.fetch(url, deadline=30, follow_redirects=False)
    if result.status_code != 200:
        raise Exception('Failed to get gipod data')

    r = json.loads(result.content)
    return r


def re_index_all():
    from plugins.gipod.bizz.manifestations import re_index_all as re_index_all_workassignments
    from plugins.gipod.bizz.workassignments import re_index_all as re_index_all_manifestations
    the_index = search.Index(name=LOCATION_INDEX)
    drop_index(the_index)
    re_index_all_workassignments()
    re_index_all_manifestations()


def find_items(lat, lng, distance, start=None, cursor=None, limit=10):

    def get_location_sort_options(lat_, lon_, distance_):
        loc_expr = "distance(location, geopoint(%f, %f))" % (lat_, lon_)
        sort_expr = search.SortExpression(expression=loc_expr,
                                          direction=search.SortExpression.ASCENDING,
                                          default_value=distance_ + 1)
        return search.SortOptions(expressions=[sort_expr])

    the_index = search.Index(name=LOCATION_INDEX)

    try:
        start_date = None
        if start and start in ('today', 'now', 'future'):
            start_date = str(datetime.today().date())
        elif start:
            start_date = start
        if lat and lng and distance:
            q = "distance(location, geopoint(%f, %f)) < %f" % (lat, lng, distance)
            if start_date:
                if start == 'future':
                    q += ' AND start_datetime >= %s' % start_date
                else:
                    q += ' AND start_datetime: %s' % start_date
            sort_options = get_location_sort_options(lat, lng, distance)
        elif start_date:
            if start == 'future':
                q = 'start_datetime >= %s' % start_date
            else:
                q = 'start_datetime: %s' % start_date
            sort_options = None
        else:
            return None

        query = search.Query(query_string=q,
                             options=search.QueryOptions(returned_fields=['id', 'location'],
                                                         sort_options=sort_options,
                                                         limit=limit,
                                                         cursor=search.Cursor(cursor)))

        search_result = the_index.search(query)
        if search_result.results:
            return search_result.results, search_result.cursor.web_safe_string if search_result.cursor else None
    except:
        logging.error('Search query error', exc_info=True)

    return None
