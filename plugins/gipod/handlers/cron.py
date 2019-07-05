# -*- coding: utf-8 -*-
# Copyright 2018 Mobicage NV
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
# @@license_version:1.3@@

import webapp2

from plugins.gipod.bizz.manifestations import sync as sync_workassignments, cleanup as cleanup_workassignments
from plugins.gipod.bizz.workassignments import sync as sync_manifestations, cleanup as cleanup_manifestations


class GipodSyncHandler(webapp2.RequestHandler):

    def get(self):
        sync_workassignments()
        sync_manifestations()


class GipodCleanupHandler(webapp2.RequestHandler):

    def get(self):
        cleanup_workassignments()
        cleanup_manifestations()
