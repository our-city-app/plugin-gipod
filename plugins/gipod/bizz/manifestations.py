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

from datetime import datetime
import logging

from dateutil.relativedelta import relativedelta
from google.appengine.api import search
from google.appengine.ext import ndb, deferred

from framework.bizz.job import run_job
from framework.utils import get_epoch_from_datetime
from framework.utils.cloud_tasks import create_task, run_tasks
from mcfw.rpc import returns, arguments
from plugins.gipod.bizz import do_request, LOCATION_INDEX
from plugins.gipod.models import ManifestationSettings, Manifestation
from plugins.gipod.plugin_consts import SYNC_QUEUE


@ndb.transactional()
def sync():
    settings = ManifestationSettings.create_key().get()
    if not settings:
        return
    last_sync = settings.synced_until
    deferred.defer(_sync_all, last_sync, _queue=SYNC_QUEUE, _transactional=True)

    settings.synced_until = datetime.now()
    settings.put()


def _sync_all(last_sync, offset=0):
    end_date = datetime.now() + relativedelta(months=12)
    params = {}
    params['enddate'] = end_date.strftime("%Y-%m-%d")
    params['limit'] = '1000'
    params['offset'] = '%s' % offset

    tasks = []
    items = do_request('/manifestation', params)
    for item in items:
        if last_sync:
            if "." in item['latestUpdate']:
                d = datetime.strptime(item['latestUpdate'], "%Y-%m-%dT%H:%M:%S.%f")
            else:
                d = datetime.strptime(item['latestUpdate'], "%Y-%m-%dT%H:%M:%S")
            if last_sync > d:
                continue

        tasks.append(create_task(_update_one, str(item['gipodId'])))

    logging.info('Scheduling update of %s manifestations', len(tasks))
    run_tasks(tasks, SYNC_QUEUE)

    if len(items) > 0:
        deferred.defer(_sync_all, last_sync, offset + len(items), _queue=SYNC_QUEUE)


def _update_one(gipod_id):
    details = do_request('/manifestation/%s' % gipod_id)

    m = Manifestation.get_by_gipod_id(gipod_id)
    if not m:
        m = Manifestation.create(gipod_id)

    m.next_start_date = None
    m.max_end_date = None

    for p in details['periods']:
        start_date = datetime.strptime(p['startDateTime'], "%Y-%m-%dT%H:%M:%S")
        if not m.next_start_date or start_date > m.next_start_date:
            m.next_start_date = start_date

        end_date = datetime.strptime(p['endDateTime'], "%Y-%m-%dT%H:%M:%S")
        if not m.max_end_date or end_date > m.max_end_date:
            m.max_end_date = end_date

    m.data = details
    m.put()

    re_index_manifestation(m)


@returns(search.Document)
@arguments(m_key=ndb.Key)
def re_index(m_key):
    m = m_key.get()
    return re_index_manifestation(m)


@returns(search.Document)
@arguments(manifestation=Manifestation)
def re_index_manifestation(manifestation):
    the_index = search.Index(name=LOCATION_INDEX)
    uid = manifestation.uid
    the_index.delete([uid])

    geo_point = search.GeoPoint(manifestation.data['location']['coordinate']['coordinates'][1],
                                manifestation.data['location']['coordinate']['coordinates'][0])

#     next_start_date = None
#     for p in manifestation.data['periods']:
#         start_date = datetime.strptime(p['startDateTime'], "%Y-%m-%dT%H:%M:%S")
#         if not next_start_date or start_date > next_start_date:
#             next_start_date = start_date

    fields = [search.AtomField(name='id', value=uid),
              search.GeoField(name='location', value=geo_point),
              search.DateField(name='start_datetime', value=manifestation.next_start_date)]

    m_doc = search.Document(doc_id=uid, fields=fields)
    the_index.put(m_doc)

    return m_doc


def re_index_all():
    run_job(re_index_query, [], re_index_worker, [])


def re_index_worker(m_key):
    re_index(m_key)


def re_index_query():
    return Manifestation.query()
