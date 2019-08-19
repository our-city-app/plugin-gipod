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

from google.appengine.api import urlfetch, search

from plugins.gipod.plugin_consts import GIPOD_API_URL, SYNC_QUEUE, NAMESPACE
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


def find_items(lat, lng, distance, start=None, end=None, cursor=None, limit=10, is_new=False, is_test=False):

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
            if start_date and end:
                if is_new:
                    q += ' AND start_datetime >= %s AND start_datetime < %s' % (start_date, end)
                else:
                    q += ' AND ((start_datetime >= %s AND start_datetime < %s) OR (start_datetime < %s AND end_datetime > %s))' % (start_date, end, start_date, start_date)
            elif start_date:
                if start == 'future' or not is_test:
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
                             options=search.QueryOptions(returned_fields=['id', 'start_datetime', 'end_datetime'],
                                                         sort_options=sort_options,
                                                         limit=limit,
                                                         cursor=search.Cursor(cursor)))
        start_time = time.time()
        search_result = the_index.search(query)
        took_time = time.time() - start_time
        logging.info('Search took {0:.3f}s'.format(took_time))
        if search_result.results:
            return search_result.results, search_result.cursor.web_safe_string if search_result.cursor else None
    except:
        logging.error('Search query error', exc_info=True)

    return None


def get_workassignment_icon(important=False):
    from framework.plugin_loader import get_config
    config = get_config(NAMESPACE)
    if important:
        path, color = '/static/plugins/gipod/icons/WorkAssignment/important_32.png', '#f10812'
    else:
        path, color = '/static/plugins/gipod/icons/WorkAssignment/nonimportant_32.png', '#eeb309'

    return config.base_url + urllib.quote(path), color


def get_manifestation_icon(event_type=None):
    from framework.plugin_loader import get_config
    config = get_config(NAMESPACE)
    icon_color = '#263583'
    path = None
    if not event_type:
        pass
    elif event_type == '(Werf)kraan':
        path = '/static/plugins/gipod/icons/Manifestation/(werf)kraan_32.png'
    elif event_type == 'Betoging':
        path = '/static/plugins/gipod/icons/Manifestation/betoging_32.png'
    elif event_type == 'Container/Werfkeet':
        path = '/static/plugins/gipod/icons/Manifestation/containerwerfkeet_32.png'
    elif event_type == 'Feest/Kermis':
        path = '/static/plugins/gipod/icons/Manifestation/feestkermis_32.png'
    elif event_type == 'Markt':
        path = '/static/plugins/gipod/icons/Manifestation/markt_32.png'
    elif event_type == 'Speelstraat':
        path = '/static/plugins/gipod/icons/Manifestation/speelstraat_32.png'
    elif event_type == 'Sportwedstrijd':
        path = '/static/plugins/gipod/icons/Manifestation/sportwedstrijd_32.png'
    elif event_type == 'Stelling':
        path = '/static/plugins/gipod/icons/Manifestation/stelling_32.png'
    elif event_type == 'Terras':
        path = '/static/plugins/gipod/icons/Manifestation/terras_32.png'
    elif event_type == 'Verhuislift':
        path = '/static/plugins/gipod/icons/Manifestation/verhuislift_32.png'
    elif event_type == 'Wielerwedstrijd - gesloten criterium':
        path = '/static/plugins/gipod/icons/Manifestation/wielerwedstrijd - gesloten criterium_32.png'
    elif event_type == 'Wielerwedstrijd - open criterium':
        path = '/static/plugins/gipod/icons/Manifestation/wielerwedstrijd - open criterium_32.png'
    else:
        path = '/static/plugins/gipod/icons/Manifestation/andere_32.png'

    return config.base_url + urllib.quote(path), icon_color
