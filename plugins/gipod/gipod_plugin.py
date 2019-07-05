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

from __future__ import unicode_literals

from framework.plugin_loader import Plugin
from framework.utils.plugins import Handler
from mcfw.consts import DEBUG
from mcfw.rpc import parse_complex_value
from plugins.gipod.handlers import GipodTestHandler
from plugins.gipod.handlers.cron import GipodSyncHandler, GipodCleanupHandler
from plugins.gipod.to import GipodPluginConfiguration


class GipodPlugin(Plugin):
    def __init__(self, configuration):
        super(GipodPlugin, self).__init__(configuration)
        self.configuration = parse_complex_value(GipodPluginConfiguration, configuration, False)
        if DEBUG:
            self.configuration.base_url = 'http://localhost:8800'

    def get_handlers(self, auth):
        if auth == Handler.AUTH_UNAUTHENTICATED:
            yield Handler(url='/plugins/gipod/test', handler=GipodTestHandler)
        if auth == Handler.AUTH_ADMIN:
            yield Handler(url='/admin/cron/gipod/sync', handler=GipodSyncHandler)
            yield Handler(url='/admin/cron/gipod/cleanup', handler=GipodCleanupHandler)
