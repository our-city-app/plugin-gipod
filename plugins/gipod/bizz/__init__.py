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

from plugins.gipod.plugin_consts import GIPOD_API_URL, SYNC_QUEUE
from plugins.gipod.to import MapItemTO, GeoPointTO, MapIconTO, MapItemDetailsTO, \
    MapGeometryCoordsListTO, MapGeometryTO, MapItemDetailSectionTO
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
    if important:
        return 'important' , '#f10812'
    else:
        return 'non_important', '#eeb309'


def get_manifestation_icon(event_type=None):
    m = {
        '(Werf)kraan': 'crane',
        'Andere': 'other',
        'Betoging': 'manifestation',
        'Container/Werfkeet': 'container',
        'Feest/Kermis': 'balloon',
        'Markt': 'basket',
        'Speelstraat': 'play_street',
        'Sportwedstrijd': 'cup',
        'Stelling': 'ladder',
        'Terras': 'glass_martini',
        'Verhuislift': 'moving_lift',
        'Wielerwedstrijd - gesloten criterium': 'cycling_circle',
        'Wielerwedstrijd - open criterium': 'cycling_line'
    }

    icon_color = '#263583'
    if event_type:
        if event_type in m:
            return m[event_type], icon_color
        else:
            logging.error('Unknown manifestation type: %s', event_type)
    return 'other', icon_color


def convert_to_item_tos(models, extras=None):
    items = []
    for m in models:
        try:
            items.append(convert_to_item_to(m, extras))
        except:
            logging.debug('uid: %s', m.uid)
            raise

    return items


def convert_to_item_to(m, extras=None):
    hindrance = m.data.get('hindrance') or {}

    if m.TYPE == 'w':
        icon_id, icon_color = get_workassignment_icon(hindrance.get('important', False))
    elif m.TYPE == 'm':
        icon_id, icon_color = get_manifestation_icon(m.data['eventType'])
    else:
        raise Exception('Unknown type: %s', m.TYPE)

    effects = hindrance.get('effects') or []

    description_message = []
    if extras and m.uid in extras:
        for p in extras[m.uid]['periods']:
            tmp_start_date = p['start']
            tmp_end_date = p['end']

            if tmp_start_date.date() == tmp_end_date.date():
                description_message.append('Op %s' % (tmp_start_date.strftime("%d/%m")))
            else:
                description_message.append('Van %s tot %s' % (tmp_start_date.strftime("%d/%m"), tmp_end_date.strftime("%d/%m")))

        if description_message:
            if effects:
                description_message.append('')
                description_message.extend(effects)

    return MapItemTO(id=m.uid,
                     coords=GeoPointTO(lat=m.data['location']['coordinate']['coordinates'][1],
                                       lon=m.data['location']['coordinate']['coordinates'][0]),
                     icon=MapIconTO(id=icon_id,
                                    color=icon_color),
                     title=m.data['description'],
                     description=u'\n'.join(description_message) if description_message else None)


def convert_to_item_details_tos(models):
    items = []
    for m in models:
        try:
            items.append(convert_to_item_details_to(m))
        except:
            logging.debug('uid: %s', m.uid)
            raise

    return items


def convert_to_item_details_to(m):
    to = MapItemDetailsTO(id=m.uid,
                          geometry=[],
                          sections=[])
    
    if  m.data['location']['geometry']['type'] == 'Polygon':
        coords_list = MapGeometryCoordsListTO(coords=[])
        for c1 in  m.data['location']['geometry']['coordinates']:
            for c in c1:
                coords_list.coords.append(GeoPointTO(lat=c[1], lon=c[0]))
                
        to.geometry.append(MapGeometryTO(type=u'Polygon',
                                         color=u'#FF0000',
                                         coords=[coords_list]))

    elif m.data['location']['geometry']['type'] == 'MultiPolygon':
        multi_coords = []
        for l1 in m.data['location']['geometry']['coordinates']:
            coords_list = MapGeometryCoordsListTO(coords=[])
            for l2 in l1:
                for c in l2:
                    coords_list.coords.append(GeoPointTO(lat=c[1], lon=c[0]))
            if coords_list.coords:
                multi_coords.append(coords_list)

        to.geometry.append(MapGeometryTO(type=u'MultiPolygon',
                                         color=u'#FF0000',
                                         coords=multi_coords))
    else:
        logging.error('Unknown geometry type: %s for %s', m.data['location']['geometry']['type'], m.uid)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    dates = []
    if m.TYPE == 'w':
        start_date = datetime.strptime(m.data['startDateTime'], "%Y-%m-%dT%H:%M:%S")
        end_date = datetime.strptime(m.data['endDateTime'], "%Y-%m-%dT%H:%M:%S")
        dates.append({'start': start_date, 'end': end_date})
    elif m.TYPE == 'm':
        for i, p in enumerate(m.data['periods']):
            end_date = datetime.strptime(p['endDateTime'], "%Y-%m-%dT%H:%M:%S")
            if end_date < today:
                continue
            start_date = datetime.strptime(p['startDateTime'], "%Y-%m-%dT%H:%M:%S")

            dates.append({'start': start_date, 'end': end_date})
            if len(dates) > 2:
                break
    else:
        raise Exception('Unknown type: %s', m.TYPE)

    if dates:
        sorted_dates = sorted(dates, key=lambda d: d['start'])
        periods_message = []
        for d in sorted_dates:
            if d['start'].time():
                start_date_str = d['start'].strftime("%d/%m %H:%M")
            else:
                start_date_str = d['start'].strftime("%d/%m")

            if d['end'].time():
                end_date_str = d['end'].strftime("%d/%m %H:%M")
            else:
                end_date_str = d['end'].strftime("%d/%m")

            periods_message.append('Van %s tot %s' % (start_date_str, end_date_str))
        
        to.sections.append(MapItemDetailSectionTO(title=None,
                                                  description=u'\n'.join(periods_message),
                                                  geometry=None))

    hindrance = m.data.get('hindrance') or {}
    effects = hindrance.get('effects') or []
    if effects:
        to.sections.append(MapItemDetailSectionTO(title=u'Hinder',
                                                  description=u'\n'.join(effects),
                                                  geometry=None))
                                   
    diversions = m.data.get('diversions') or []
    if diversions:
        for i, diversion in enumerate(diversions):
            diversions_message = []
            diversion_types = diversion.get('diversionTypes') or []
            if diversion_types:
                diversions_message.append('Deze omleiding is geldig voor:\n%s' % ('\n'.join(diversion_types)))
            diversion_streets = diversion.get('streets') or []
            if diversion_streets:
                diversions_message.append('U kan ook volgende straten volgen:\n%s' % ('\n'.join(diversion_streets)))

            coords_list = MapGeometryCoordsListTO(coords=[])
            if  diversion['geometry']['type'] == 'LineString':
                for c in  diversion['geometry']['coordinates']:
                    coords_list.coords.append(GeoPointTO(lat=c[1], lon=c[0]))
            else:
                logging.error('Unknown diversion geometry type: %s for %s', diversion['geometry']['type'], m.uid)

            if coords_list.coords:
                geometry = MapGeometryTO(type=u'LineString',
                                         color=u'#00FF00',
                                         coords=[coords_list])
            else:
                geometry = None

            to.sections.append(MapItemDetailSectionTO(title=u'Omleiding %s' % (i + 1),
                                                      description=u'\n'.join(diversions_message),
                                                      geometry=geometry))

    return to
