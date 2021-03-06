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

from google.appengine.ext import ndb
from mcfw.consts import DEBUG

from framework.models.common import NdbModel
from plugins.gipod.plugin_consts import NAMESPACE


class ItemFilterType(object):
    RANGE = 'range'
    START_DATE = 'start_date'


class SyncSettings(NdbModel):  # for both work assignments and manifestations
    NAMESPACE = NAMESPACE

    synced_until = ndb.DateTimeProperty()

    @classmethod
    def create_key(cls):
        return ndb.Key(cls, 'SyncSettings', namespace=cls.NAMESPACE)


class BaseModel(NdbModel):
    NAMESPACE = NAMESPACE
    TYPE_WORK_ASSIGNMENT = u'w'
    TYPE_MANIFESTATION = u'm'

    cleanup_date = ndb.DateTimeProperty()

    data = ndb.JsonProperty(indexed=False)

    @property
    def uid(self):
        return self.key.id()

    @property
    def gipod_id(self):
        return self.uid.split('-')[1]

    @classmethod
    def create_key(cls, type_, gipod_id):
        if type_ not in (cls.TYPE_WORK_ASSIGNMENT, cls.TYPE_MANIFESTATION):
            raise Exception('incorrect type')
        id_ = u'%s-%s' % (type_, gipod_id)
        return ndb.Key(cls, id_, namespace=cls.NAMESPACE)

    @classmethod
    def list_timed_out(cls, current_date):
        return cls.query()\
            .filter(cls.cleanup_date != None)\
            .filter(cls.cleanup_date < current_date)\
            .order(cls.cleanup_date, cls.key)

    @classmethod
    def list(cls):
        return cls.query()


class WorkAssignment(BaseModel):
    TYPE = BaseModel.TYPE_WORK_ASSIGNMENT


class Manifestation(BaseModel):
    TYPE = BaseModel.TYPE_MANIFESTATION


class Consumer(NdbModel):
    NAMESPACE = NAMESPACE

    ref = ndb.StringProperty(indexed=False)

    @property
    def consumer_key(self):
        return self.key.id().decode('utf8')

    @classmethod
    def create_key(cls, consumer_key):
        return ndb.Key(cls, consumer_key, namespace=cls.NAMESPACE)


class ElasticsearchSettings(NdbModel):
    NAMESPACE = NAMESPACE

    base_url = ndb.StringProperty(indexed=False)

    auth_username = ndb.StringProperty(indexed=False)
    auth_password = ndb.StringProperty(indexed=False)
    items_index = ndb.StringProperty(default=None if DEBUG else 'gipod', indexed=False)

    @classmethod
    def create_key(cls):
        return ndb.Key(cls, u'ElasticsearchSettings', namespace=cls.NAMESPACE)


class MapUser(NdbModel):
    NAMESPACE = NAMESPACE

    app_id = ndb.StringProperty()
    last_load_request = ndb.DateTimeProperty()

    @property
    def user_id(self):
        return self.key.id().decode('utf8')

    @classmethod
    def create_key(cls, user_id):
        return ndb.Key(cls, user_id, namespace=cls.NAMESPACE)

