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

from plugins.gipod.bizz.manifestations import sync as sync_manifestations, \
    cleanup_timed_out as cleanup_timed_out_manifestations, \
    cleanup_deleted as cleanup_deleted_manifestations
from plugins.gipod.bizz.workassignments import sync as sync_workassignments, \
    cleanup_timed_out as cleanup_timed_out_workassignments, \
    cleanup_deleted as cleanup_deleted_workassignments


class GipodSyncHandler(webapp2.RequestHandler):

    def get(self):
        sync_workassignments()
        sync_manifestations()


class GipodCleanupTimedOutHandler(webapp2.RequestHandler):

    def get(self):
        cleanup_timed_out_workassignments()
        cleanup_timed_out_manifestations()


class GipodCleanupDeletedHandler(webapp2.RequestHandler):

    def get(self):
        cleanup_deleted_workassignments()
        cleanup_deleted_manifestations()
