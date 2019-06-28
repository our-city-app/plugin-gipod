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


class WorkAssignment(NdbModel):
    NAMESPACE = NAMESPACE

    gipod_id = ndb.StringProperty()

    start_date = ndb.DateTimeProperty()
    end_date = ndb.DateTimeProperty()

    data = ndb.JsonProperty(compressed=True)

    @property
    def workassignment_id(self):
        return self.key.id()

    @property
    def uid(self):
        return u'w-%s' % (self.workassignment_id)
    
    @classmethod
    def create_key(cls, id_):
        return ndb.Key(cls, id_, namespace=cls.NAMESPACE)

    @classmethod
    def create(cls, gipod_id):
        return cls(gipod_id=gipod_id,
                   namespace=cls.NAMESPACE)

    @classmethod
    def get_by_gipod_id(cls, gipod_id):
        return cls.query().filter(cls.gipod_id == gipod_id).get()


class Manifestation(NdbModel):
    NAMESPACE = NAMESPACE

    gipod_id = ndb.StringProperty()

    next_start_date = ndb.DateTimeProperty()
    max_end_date = ndb.DateTimeProperty()

    data = ndb.JsonProperty(compressed=True)

    @property
    def manifestation_id(self):
        return self.key.id()

    @property
    def uid(self):
        return u'm-%s' % (self.manifestation_id)

    @classmethod
    def create_key(cls, id_):
        return ndb.Key(cls, id_, namespace=cls.NAMESPACE)

    @classmethod
    def create(cls, gipod_id):
        return cls(gipod_id=gipod_id,
                   namespace=cls.NAMESPACE)

    @classmethod
    def get_by_gipod_id(cls, gipod_id):
        return cls.query().filter(cls.gipod_id == gipod_id).get()
