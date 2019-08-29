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

from framework.to import TO
from mcfw.properties import unicode_property, float_property, typed_property, \
    long_property, object_factory


class GipodPluginConfiguration(TO):
    base_url = unicode_property('base_url')
    google_maps_key = unicode_property('google_maps_key')


class GeoPointTO(TO):
    lat = float_property('1')
    lon = float_property('2')


class MapGeometryObjectType(object):
    LINE_STRING = 'LineString'
    MULTI_LINE_STRING = 'MultiLineString'
    POLYGON = 'Polygon'
    MULTI_POLYGON = 'MultiPolygon'


class CoordsListTO(TO):
    coords = typed_property('coords', GeoPointTO, True)


class PolygonTO(TO):
    rings = typed_property('rings', CoordsListTO, True)


class LineStringTypeTO(TO):
    type = unicode_property('type', default=MapGeometryObjectType.LINE_STRING)
    color = unicode_property('color')
    line = typed_property('line', CoordsListTO, False)


class MultiLineStringTypeTO(TO):
    type = unicode_property('type', default=MapGeometryObjectType.MULTI_LINE_STRING)
    color = unicode_property('color')
    lines = typed_property('lines', CoordsListTO, True)


class PolygonTypeTO(PolygonTO):
    type = unicode_property('type', default=MapGeometryObjectType.POLYGON)
    color = unicode_property('color')


class MultiPolygonTypeTO(TO):
    type = unicode_property('type', default=MapGeometryObjectType.MULTI_POLYGON)
    color = unicode_property('color')
    polygons = typed_property('polygons', PolygonTO, True)


MAP_GEOMETRY_OBJECT_MAPPING = {
    MapGeometryObjectType.LINE_STRING: LineStringTypeTO,
    MapGeometryObjectType.MULTI_LINE_STRING: MultiLineStringTypeTO,
    MapGeometryObjectType.POLYGON: PolygonTypeTO,
    MapGeometryObjectType.MULTI_POLYGON: MultiPolygonTypeTO,
}


class MapGeometryObjectTO(object_factory):
    type = unicode_property('type')

    def __init__(self):
        super(MapGeometryObjectTO, self).__init__('type', MAP_GEOMETRY_OBJECT_MAPPING)


class MapIconTO(TO):
    id = unicode_property('1')
    color = unicode_property('2')


class MapItemDetailSectionTO(TO):
    title = unicode_property('1')
    description = unicode_property('2')
    geometry = typed_property('3', MapGeometryObjectTO(), False)


class MapItemTO(TO):
    id = unicode_property('1')
    coords = typed_property('2', GeoPointTO, False)
    icon = typed_property('3', MapIconTO, False)
    title = unicode_property('4')
    description = unicode_property('5')


class MapItemDetailsTO(TO):
    id = unicode_property('1')
    geometry = typed_property('2', MapGeometryObjectTO(), True)
    sections = typed_property('3', MapItemDetailSectionTO, True)


class GetMapItemsResponseTO(TO):
    cursor = unicode_property('1')
    items = typed_property('2', MapItemTO, True)
    distance = long_property('3')


class GetMapItemDetailsResponseTO(TO):
    items = typed_property('1', MapItemDetailsTO, True)
