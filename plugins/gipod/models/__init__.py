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

from google.appengine.ext import ndb

from framework.models.common import NdbModel
from plugins.gipod.plugin_consts import NAMESPACE


class WorkAssignmentSettings(NdbModel):
    NAMESPACE = NAMESPACE

    synced_until = ndb.DateTimeProperty()

    @classmethod
    def create_key(cls):
        return ndb.Key(cls, u'WorkAssignmentSettings', namespace=cls.NAMESPACE)


class ManifestationSettings(NdbModel):
    NAMESPACE = NAMESPACE

    synced_until = ndb.DateTimeProperty()

    @classmethod
    def create_key(cls):
        return ndb.Key(cls, u'ManifestationSettings', namespace=cls.NAMESPACE)


class BaseModel(NdbModel):
    NAMESPACE = NAMESPACE
    TYPE_WORK_ASSIGNMENT = u'w'
    TYPE_MANIFESTATION = u'm'

    cleanup_date = ndb.DateTimeProperty()
    search_keys = ndb.StringProperty(indexed=False, repeated=True)

    data = ndb.JsonProperty(compressed=True)
    
    @property
    def uid(self):
        return self.key.id()

    @classmethod
    def create_key(cls, type_, gipod_id):
        if type_ not in (cls.TYPE_WORK_ASSIGNMENT, cls.TYPE_MANIFESTATION):
            raise Exception('incorrect type')
        id_ = u'%s-%s' % (type_, gipod_id)
        return ndb.Key(cls, id_, namespace=cls.NAMESPACE)


class WorkAssignment(BaseModel):
    TYPE = BaseModel.TYPE_WORK_ASSIGNMENT


class Manifestation(BaseModel):
    TYPE = BaseModel.TYPE_MANIFESTATION
