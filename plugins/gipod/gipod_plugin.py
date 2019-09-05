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

from framework.plugin_loader import Plugin
from framework.utils.plugins import Handler
from mcfw.consts import DEBUG
from mcfw.rpc import parse_complex_value
from plugins.gipod.handlers import GipodItemsHandler, GipodNewItemsHandler, \
    GipodItemDetailsHandler
from plugins.gipod.handlers.cron import GipodCleanupTimedOutHandler, GipodCleanupDeletedHandler, \
    GipodSyncHandler
from plugins.gipod.handlers.preview import GipodPreviewHandler
from plugins.gipod.to import GipodPluginConfiguration


class GipodPlugin(Plugin):
    def __init__(self, configuration):
        super(GipodPlugin, self).__init__(configuration)
        self.configuration = parse_complex_value(GipodPluginConfiguration, configuration, False)
        if DEBUG:
            self.configuration.base_url = 'http://localhost:8800'

    def get_handlers(self, auth):
        if auth == Handler.AUTH_UNAUTHENTICATED:
            yield Handler(url='/plugins/gipod/items', handler=GipodItemsHandler)
            yield Handler(url='/plugins/gipod/items/new', handler=GipodNewItemsHandler)
            yield Handler(url='/plugins/gipod/items/detail', handler=GipodItemDetailsHandler)
        if auth == Handler.AUTH_ADMIN:
            yield Handler(url='/admin/cron/gipod/cleanup/timed_out', handler=GipodCleanupTimedOutHandler)
            yield Handler(url='/admin/cron/gipod/cleanup/deleted', handler=GipodCleanupDeletedHandler)
            yield Handler(url='/admin/cron/gipod/sync', handler=GipodSyncHandler)
            yield Handler(url='/admin/gipod/preview', handler=GipodPreviewHandler)
