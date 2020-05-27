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
from __future__ import unicode_literals

import json
import logging
import urllib
from datetime import datetime

from dateutil.parser import parse as parse_datetime
from google.appengine.api import urlfetch
from typing import Union, List, Iterable

from plugins.gipod.models import Manifestation, WorkAssignment, MapUser
from plugins.gipod.plugin_consts import GIPOD_API_URL
from plugins.gipod.to import MapItemTO, GeoPointTO, MapIconTO, MapItemDetailsTO, CoordsListTO, \
    PolygonGeometryTO, MultiPolygonGeometryTO, PolygonTO, LineStringGeometryTO, MultiLineStringGeometryTO, \
    TextSectionTO, GeometrySectionTO
from plugins.gipod.utils import get_app_id_from_user_id

NOT_IMPORTANT_COLOR = '#eeb309'


def do_request_without_processing(relative_url, params=None):
    # type: (str, dict) -> urlfetch._URLFetchResult
    url = '%s%s' % (GIPOD_API_URL, relative_url)
    if params:
        query_params = urllib.urlencode(params)
        if query_params:
            url = '%s?%s' % (url, query_params)

    logging.info('do_request: %s', url)

    return urlfetch.fetch(url, deadline=30, follow_redirects=False)


def do_request(relative_url, params=None):
    result = do_request_without_processing(relative_url, params)
    if result.status_code != 200:
        raise Exception('Failed to get gipod data')

    r = json.loads(result.content)
    return r


def validate_and_clean_data(type_, uid, data):
    if type_ == Manifestation.TYPE:
        get_manifestation_icon(data['eventType'])
    data['location']['coordinate']['coordinates'] = _clean_coordinates(data['location']['coordinate']['coordinates'])
    if data['location']['geometry']['type'] in ('GeometryCollection',):
        for g in data['location']['geometry']['geometries']:
            if g['type'] not in ('Polygon', 'MultiPolygon',):
                logging.error('Unknown geometry collection type: "%s" for %s', g['type'], uid)
            else:
                _clean_geometry(g)
    elif data['location']['geometry']['type'] not in ('Polygon', 'MultiPolygon',):
        logging.error('Unknown geometry type: "%s" for %s', data['location']['geometry']['type'], uid)
    else:
        _clean_geometry(data['location']['geometry'])

    diversions = data.get('diversions') or []
    for diversion in diversions:
        if diversion['geometry']['type'] in ('GeometryCollection',):
            for g in diversion['geometry']['geometries']:
                if g['type'] not in ('LineString', 'MultiLineString',):
                    logging.error('Unknown diversion geometry type: "%s" for %s', diversion['geometry']['type'], uid)
                else:
                    _clean_geometry(g)
        elif diversion['geometry']['type'] not in ('LineString', 'MultiLineString',):
            logging.error('Unknown diversion geometry type: "%s" for %s', diversion['geometry']['type'], uid)
        else:
            _clean_geometry(diversion['geometry'])


def _clean_geometry(geometry):
    if geometry['type'] == 'GeometryCollection':
        for item in geometry['geometries']:
            _clean_geometry(item)
    elif geometry['type'] in ('LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'):
        _clean_coordinates(geometry['coordinates'])


# Removes unnecessary decimals (some were up to 16 decimals long!) from the coordinates (https://xkcd.com/2170)
def _clean_coordinates(coordinates_list):
    for i, item in enumerate(coordinates_list):
        if isinstance(item, list):
            coordinates_list[i] = _clean_coordinates(item)
        elif isinstance(item, float):
            coordinates_list[i] = round(item, 6)  # 6 decimals -> 0.11m per unit
        else:
            logging.warn('_clean_coordinates unknown prop type:%s', type(item))

    return coordinates_list


def get_workassignment_icon(important=False):
    if important:
        return 'important', '#f10812'
    else:
        return 'non_important', NOT_IMPORTANT_COLOR


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
        event_type = event_type.strip()
        if event_type in m:
            return m[event_type], icon_color
        else:
            logging.error('Unknown manifestation type: "%s"', event_type)
    return 'other', icon_color


def convert_to_item_tos(models):
    # type: (Iterable[Union[WorkAssignment, Manifestation]]) -> List[MapItemTO]
    items = []
    now_ = datetime.utcnow()
    for m in models:
        try:
            items.append(convert_to_item_to(m, now_))
        except:
            logging.debug('uid: %s', m.uid)
            raise

    return items


def convert_to_item_to(model, now_):
    hindrance = model.data.get('hindrance') or {}

    if isinstance(model, Manifestation):
        description = None
        icon_id, icon_color = get_manifestation_icon(model.data['eventType'])
        # Sort by start date
        sorted_periods = sorted(((parse_datetime(p['startDateTime']), parse_datetime(p['endDateTime']))
                                 for p in model.data.get('periods', [])), key=lambda a: a[0])
        for start_date, end_date in sorted_periods:
            # Skip dates in the past
            if end_date < now_:
                continue
            description = period_to_string(now_, start_date, end_date, False)
            break
    elif isinstance(model, WorkAssignment):
        icon_id, icon_color = get_workassignment_icon(hindrance.get('important', False))
        start_date = parse_datetime(model.data['startDateTime'])
        end_date = parse_datetime(model.data['endDateTime'])
        description = period_to_string(now_, start_date, end_date, False)
    else:
        raise Exception('Unknown item type %s' % model)

    return MapItemTO(id=model.uid,
                     coords=GeoPointTO(lat=model.data['location']['coordinate']['coordinates'][1],
                                       lon=model.data['location']['coordinate']['coordinates'][0]),
                     icon=MapIconTO(id=icon_id,
                                    color=icon_color),
                     title=model.data['description'],
                     description=description)


def period_to_string(now_, start_date, end_date, include_time):
    # type: (datetime, datetime, datetime, bool) -> unicode
    start_date_str = start_date.strftime(get_date_format(now_, start_date, include_time))
    if include_time:
        if start_date.date() == end_date.date() and start_date.time() == end_date.time():
            return 'Op %s' % start_date_str
    elif start_date.date() == end_date.date():
        return 'Op %s' % start_date_str
    end_date_str = end_date.strftime(get_date_format(now_, end_date, include_time))
    return 'Van %s tot %s' % (start_date_str, end_date_str)


def get_date_format(now, date, include_time):
    # type: (datetime, datetime, bool) -> unicode
    if date.time() and include_time:
        if now.year == date.year:
            return '%d/%m %H:%M'
        else:
            return '%d/%m/%Y %H:%M'
    if now.year == date.year:
        return '%d/%m'
    return '%d/%m/%Y'


def convert_to_item_details_tos(uids, models):
    items = []
    current_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    for uid, m in zip(uids, models):
        try:
            items.append(convert_to_item_details_to(uid, m, current_date))
        except:
            logging.debug('uid: %s', uid)
            raise

    return items


def get_geometry_to(data, color):
    if data['type'] == 'LineString':
        return LineStringGeometryTO(
            color=color,
            line=CoordsListTO(
                coords=[GeoPointTO(lat=c[1], lon=c[0]) for c in data['coordinates']]
            )
        )
    elif data['type'] == 'MultiLineString':
        return MultiLineStringGeometryTO(
            color=color,
            lines=[CoordsListTO(coords=[GeoPointTO(lat=c[1], lon=c[0]) for c in list_of_coords])
                   for list_of_coords in data['coordinates'] if list_of_coords]
        )
    elif data['type'] == 'Polygon':
        return PolygonGeometryTO(
            color=color,
            rings=[CoordsListTO(coords=[GeoPointTO(lat=c[1], lon=c[0]) for c in list_of_coords])
                   for list_of_coords in data['coordinates'] if list_of_coords]
        )
    elif data['type'] == 'MultiPolygon':
        multi_polygon = MultiPolygonGeometryTO(color=color, polygons=[])
        for nested_coordinates in data['coordinates']:
            if nested_coordinates:
                multi_polygon.polygons.append(PolygonTO(
                    rings=[CoordsListTO(coords=[GeoPointTO(lat=c[1], lon=c[0]) for c in list_of_coords])
                           for list_of_coords in nested_coordinates if list_of_coords]
                ))
        return multi_polygon
    else:
        return None


def get_geometry_tos(uid, data, color):
    if data['type'] in ('LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'):
        return [get_geometry_to(data, color)]
    elif data['type'] == 'GeometryCollection':
        geo_list = []
        for g in data['geometries']:
            to = get_geometry_to(g, color)
            if to:
                geo_list.append(to)
            else:
                logging.error('Unknown geometry collection  type: "%s" for %s', g['type'], uid)
        return geo_list

    logging.error('Unknown geometry type: "%s" for %s', data['type'], uid)
    return []


def convert_to_item_details_to(uid, model, current_date):
    # type: (str, Union[WorkAssignment, Manifestation], datetime) -> MapItemDetailsTO
    to = MapItemDetailsTO(id=uid,
                          geometry=[],
                          sections=[])
    if isinstance(model, WorkAssignment):
        _, icon_color = get_workassignment_icon(model.data.get('hindrance', {}).get('important', False))
    elif isinstance(model, Manifestation):
        _, icon_color = get_manifestation_icon(model.data['eventType'])
    elif model is None:
        # Chances of this happening *should* be very low
        # This should only happen when user has the map open for a long time,
        # and he clicks on an item that has been deleted in the mean time
        to.sections = [TextSectionTO(title='Verwijderd',
                                     description='Dit item bestaat niet meer')]
        return to
    else:
        raise Exception('Unknown type: %s', model)

    to.geometry = get_geometry_tos(uid, model.data['location']['geometry'], icon_color)

    dates = []
    if isinstance(model, WorkAssignment):
        start_date = datetime.strptime(model.data['startDateTime'], "%Y-%m-%dT%H:%M:%S")
        end_date = datetime.strptime(model.data['endDateTime'], "%Y-%m-%dT%H:%M:%S")
        dates.append({'start': start_date, 'end': end_date})
    elif isinstance(model, Manifestation):
        for i, p in enumerate(model.data['periods']):
            end_date = datetime.strptime(p['endDateTime'], "%Y-%m-%dT%H:%M:%S")
            if end_date < current_date:
                continue
            start_date = datetime.strptime(p['startDateTime'], "%Y-%m-%dT%H:%M:%S")

            dates.append({'start': start_date, 'end': end_date})
            if len(dates) > 2:
                break
    if dates:
        sorted_dates = sorted(dates, key=lambda d: d['start'])
        periods_message = []
        for d in sorted_dates:
            periods_message.append(period_to_string(current_date, d['start'], d['end'], True))

        contact_details = model.data.get('contactDetails') or {}
        if contact_details.get('organisation'):
            if model.data.get('type'):
                periods_message.append('%s - %s' % (model.data['type'], contact_details['organisation']))
            else:
                periods_message.append(contact_details['organisation'])

        to.sections.append(TextSectionTO(title=None,
                                         description='\n'.join(periods_message)))

    effects = model.data.get('hindrance', {}).get('effects') or []
    if effects:
        description_lines = []
        for effect in effects:
            description_lines.append('- %s' % effect)
        to.sections.append(TextSectionTO(title='Hinder',
                                         description='\n'.join(description_lines)))

    diversions = model.data.get('diversions') or []
    for i, diversion in enumerate(diversions):
        lines = []
        diversion_types = diversion.get('diversionTypes') or []
        if diversion_types:
            lines.append('Deze omleiding is geldig voor:')
            for t in diversion_types:
                lines.append('- %s' % t)
        diversion_streets = diversion.get('streets') or []
        if diversion_streets:
            lines.append('Deze omleiding loopt via de volgende straten:')
            for street in diversion_streets:
                lines.append('- %s' % street)
        title = 'Omleiding %d' % (i + 1) if len(diversions) > 1 else 'Omleiding'
        to.sections.append(GeometrySectionTO(title=title,
                                             description='\n'.join(lines),
                                             geometry=get_geometry_tos(model.uid, diversion['geometry'], '#2dc219')))

    return to


def save_last_load_map_request(user_id, d):
    key = MapUser.create_key(user_id)
    map_user = key.get()
    if not map_user:
        map_user = MapUser(key=key)
        map_user.app_id = get_app_id_from_user_id(user_id)

    if map_user.last_load_request and map_user.last_load_request > d:
        return

    map_user.last_load_request = d
    map_user.put()
