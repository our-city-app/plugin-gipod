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
    long_property


class GipodPluginConfiguration(TO):
    base_url = unicode_property('base_url')
    google_maps_key = unicode_property('google_maps_key')


class GeoPointTO(TO):
    lat = float_property('1')
    lon = float_property('2')


class MapGeometryCoordsListTO(TO):
    coords = typed_property('1', GeoPointTO, True)


class MapGeometryTO(TO):
    type = unicode_property('1')
    color = unicode_property('2')
    coords = typed_property('3', MapGeometryCoordsListTO, True)


class MapItemLocationTO(TO):
    coords = typed_property('1', GeoPointTO, False)
    geometry = typed_property('2', MapGeometryTO, True)


class MapIconTO(TO):
    id = unicode_property('1')
    color = unicode_property('2')


class MapItemDetailSectionTO(TO):
    title = unicode_property('1')
    description = unicode_property('2')
    geometry = typed_property('3', MapGeometryTO, False)


class MapItemDetailTO(TO):
    sections = typed_property('1', MapItemDetailSectionTO, True)


class MapItemTO(TO):
    id = unicode_property('1')
    location = typed_property('2', MapItemLocationTO, False)
    icon = typed_property('3', MapIconTO, False)
    title = unicode_property('4')
    description = unicode_property('5')
    detail = typed_property('6', MapItemDetailTO, False)


class MapBaseUrlsTO(TO):
    icon_pin = unicode_property('1')
    icon_transparent = unicode_property('1')


class GetMapItemsResponseTO(TO):
    cursor = unicode_property('1')
    items = typed_property('2', MapItemTO, True)
    distance = long_property('3')
    base_urls = typed_property('4', MapBaseUrlsTO, False)
