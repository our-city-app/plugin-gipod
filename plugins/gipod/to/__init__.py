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

from framework.to import TO
from mcfw.properties import unicode_property, float_property, typed_property, \
    long_property, object_factory


class GipodPluginConfiguration(TO):
    base_url = unicode_property('base_url')
    google_maps_key = unicode_property('google_maps_key')


class GeoPointTO(TO):
    lat = float_property('1')
    lon = float_property('2')


class MapGeometryType(object):
    LINE_STRING = 'LineString'
    MULTI_LINE_STRING = 'MultiLineString'
    POLYGON = 'Polygon'
    MULTI_POLYGON = 'MultiPolygon'


class CoordsListTO(TO):
    coords = typed_property('coords', GeoPointTO, True)


class PolygonTO(TO):
    rings = typed_property('rings', CoordsListTO, True)


class LineStringGeometryTO(TO):
    type = unicode_property('type', default=MapGeometryType.LINE_STRING)
    color = unicode_property('color')
    line = typed_property('line', CoordsListTO, False)


class MultiLineStringGeometryTO(TO):
    type = unicode_property('type', default=MapGeometryType.MULTI_LINE_STRING)
    color = unicode_property('color')
    lines = typed_property('lines', CoordsListTO, True)


class PolygonGeometryTO(PolygonTO):
    type = unicode_property('type', default=MapGeometryType.POLYGON)
    color = unicode_property('color')


class MultiPolygonGeometryTO(TO):
    type = unicode_property('type', default=MapGeometryType.MULTI_POLYGON)
    color = unicode_property('color')
    polygons = typed_property('polygons', PolygonTO, True)


MAP_GEOMETRY_MAPPING = {
    MapGeometryType.LINE_STRING: LineStringGeometryTO,
    MapGeometryType.MULTI_LINE_STRING: MultiLineStringGeometryTO,
    MapGeometryType.POLYGON: PolygonGeometryTO,
    MapGeometryType.MULTI_POLYGON: MultiPolygonGeometryTO,
}


class MapGeometryTO(object_factory):
    type = unicode_property('type')
    color = unicode_property('color')

    def __init__(self):
        super(MapGeometryTO, self).__init__('type', MAP_GEOMETRY_MAPPING)


class MapSectionType(object):
    TEXT = 'text'
    GEOMETRY = 'geometry'


class TextSectionTO(TO):
    type = unicode_property('type', default=MapSectionType.TEXT)
    title = unicode_property('title')
    description = unicode_property('description')


class GeometrySectionTO(TO):
    type = unicode_property('type', default=MapSectionType.GEOMETRY)
    title = unicode_property('title')
    description = unicode_property('description')
    geometry = typed_property('geometry', MapGeometryTO(), True)


MAP_SECTION_MAPPING = {
    MapSectionType.TEXT: TextSectionTO,
    MapSectionType.GEOMETRY: GeometrySectionTO,
}


class MapSectionTO(object_factory):
    type = unicode_property('type')

    def __init__(self):
        super(MapSectionTO, self).__init__('type', MAP_SECTION_MAPPING)


class MapIconTO(TO):
    id = unicode_property('1')
    color = unicode_property('2')


class MapItemTO(TO):
    id = unicode_property('1')
    coords = typed_property('2', GeoPointTO, False)
    icon = typed_property('3', MapIconTO, False)
    title = unicode_property('4')
    description = unicode_property('5')


class MapItemDetailsTO(TO):
    id = unicode_property('id')
    geometry = typed_property('geometry', MapGeometryTO(), True)
    sections = typed_property('sections', MapSectionTO(), True)


class GetMapItemsResponseTO(TO):
    cursor = unicode_property('1')
    items = typed_property('2', MapItemTO, True)
    distance = long_property('3')


class GetMapItemDetailsResponseTO(TO):
    items = typed_property('1', MapItemDetailsTO, True)
