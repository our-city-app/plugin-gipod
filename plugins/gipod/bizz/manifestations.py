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
from framework.utils.cloud_tasks import create_task, run_tasks
from mcfw.consts import DEBUG
from mcfw.rpc import returns, arguments
from plugins.gipod.bizz import do_request, LOCATION_INDEX, \
    validate_and_clean_data, do_request_without_processing
from plugins.gipod.bizz.elasticsearch import index_docs, delete_docs
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


def cleanup_timed_out():
    run_job(cleanup_timed_out_query, [], cleanup_timed_out_worker, [])


def cleanup_deleted():
    run_job(cleanup_deleted_query, [], cleanup_deleted_worker, [])


def _sync_all(last_sync, offset=0):
    end_date = datetime.now() + relativedelta(months=1 if DEBUG else 12)
    params = {}
    params['enddate'] = end_date.strftime("%Y-%m-%d")
    params['limit'] = '1000'
    params['offset'] = '%s' % offset

    tasks = []
    skip_tasks = []
    items = do_request('/manifestation', params)
    for item in items:
        if last_sync:
            if "." in item['latestUpdate']:
                d = datetime.strptime(item['latestUpdate'], "%Y-%m-%dT%H:%M:%S.%f")
            else:
                d = datetime.strptime(item['latestUpdate'], "%Y-%m-%dT%H:%M:%S")
            if last_sync > d:
                skip_tasks.append(create_task(_update_one, str(item['gipodId']), skip_if_exists=True))
                continue

        tasks.append(create_task(_update_one, str(item['gipodId'])))

    logging.info('Scheduling update of %s manifestations', len(tasks))
    run_tasks(tasks, SYNC_QUEUE)
    run_tasks(skip_tasks, SYNC_QUEUE)

    if len(items) > 0:
        deferred.defer(_sync_all, last_sync, offset + len(items), _queue=SYNC_QUEUE)


def _update_one(gipod_id, skip_if_exists=False):
    m_key = Manifestation.create_key(Manifestation.TYPE, gipod_id)
    m = m_key.get()
    if m and skip_if_exists:
        return
    if not m:
        m = Manifestation(key=m_key)

    m.data = do_request('/manifestation/%s' % gipod_id)
    validate_and_clean_data(m.TYPE, m.uid, m.data)
    re_index_manifestation(m)


@returns([search.Document])
@arguments(m_key=ndb.Key, index_types=[unicode])
def re_index(m_key, index_types=None):
    m = m_key.get()
    return re_index_manifestation(m, index_types=index_types)


@returns([search.Document])
@arguments(manifestation=Manifestation, index_types=[unicode])
def re_index_manifestation(manifestation, index_types=None):
    if not index_types:
        index_types = ['search', 'elasticsearch']

    the_index = search.Index(name=LOCATION_INDEX)
    if 'search' in index_types:
        the_index.delete(manifestation.search_keys)
    if 'elasticsearch' in index_types:
        delete_docs(manifestation.search_keys)

    geo_point = search.GeoPoint(manifestation.data['location']['coordinate']['coordinates'][1],
                                manifestation.data['location']['coordinate']['coordinates'][0])

    manifestation.visible = False
    manifestation.cleanup_date = None
    manifestation.search_keys = []
    m_docs = []
    docs = []
    now_ = datetime.utcnow()

    for i, p in enumerate(manifestation.data['periods']):
        end_date = datetime.strptime(p['endDateTime'], "%Y-%m-%dT%H:%M:%S")
        if end_date <= now_:
            continue

        manifestation.visible = True
        if not manifestation.cleanup_date or manifestation.cleanup_date > end_date:
            manifestation.cleanup_date = end_date
        uid = u'%s-%s' % (manifestation.uid, i)
        manifestation.search_keys.append(uid)


        start_date = datetime.strptime(p['startDateTime'], "%Y-%m-%dT%H:%M:%S")
        fields = [
            search.AtomField(name='id', value=uid),
            search.GeoField(name='location', value=geo_point),
            search.DateField(name='start_datetime', value=start_date),
            search.DateField(name='end_datetime', value=end_date)
        ]

        m_docs.append(search.Document(doc_id=uid, fields=fields))

        doc = {
            "location": {
                "lat": manifestation.data['location']['coordinate']['coordinates'][1],
                "lon": manifestation.data['location']['coordinate']['coordinates'][0]
            },
            "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
            "time_frame": {
                "gte" : start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "lte" : end_date.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        docs.append({'uid': uid, 'data': doc})

    manifestation.put()
    if 'search' in index_types and m_docs:
        the_index.put(m_docs)
    if 'elasticsearch' in index_types and docs:
        index_docs(docs)
    return m_docs


def re_index_all(index_types=None):
    run_job(re_index_query, [], re_index_worker, [index_types])


def re_index_worker(m_key, index_types=None):
    re_index(m_key, index_types=index_types)


def re_index_query():
    return Manifestation.query()


def cleanup_timed_out_worker(m_key):
    re_index(m_key)


def cleanup_timed_out_query():
    qry = Manifestation.query()
    qry = qry.filter(Manifestation.cleanup_date != None)
    qry = qry.filter(Manifestation.cleanup_date < datetime.utcnow())
    qry = qry.order(Manifestation.cleanup_date, Manifestation.key)
    return qry


def cleanup_deleted_worker(m_key):
    uid = m_key.id()
    gipod_id = uid.split('-')[1]
    result = do_request_without_processing('/manifestation/%s' % gipod_id)
    if result.status_code == 200:
        return
    if result.status_code != 404:
        logging.warn('cleanup_deleted_worker failed for %s with status code %s', uid, result.status_code)
        return
    logging.debug('cleanup_deleted_worker deleted %s', uid)

    m = m_key.get()

    the_index = search.Index(name=LOCATION_INDEX)
    the_index.delete(m.search_keys)
    delete_docs(m.search_keys)

    m.cleanup_date = None
    m.search_keys = []
    m.visible = False
    m.put()


def cleanup_deleted_query():
    qry = Manifestation.query()
    qry = qry.filter(Manifestation.visible == True)
    return qry
