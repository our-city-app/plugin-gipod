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

from datetime import datetime
import logging

from dateutil.relativedelta import relativedelta
from google.appengine.ext import ndb, deferred

from framework.bizz.job import run_job
from framework.utils.cloud_tasks import create_task, run_tasks
from mcfw.consts import DEBUG
from mcfw.rpc import returns, arguments
from plugins.gipod.bizz import do_request, validate_and_clean_data, do_request_without_processing
from plugins.gipod.bizz.elasticsearch import index_doc, delete_docs
from plugins.gipod.models import WorkAssignmentSettings, WorkAssignment
from plugins.gipod.plugin_consts import SYNC_QUEUE


@ndb.transactional()
def sync():
    settings = WorkAssignmentSettings.create_key().get()
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
    items = do_request('/workassignment', params)
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

    logging.info('Scheduling update of %s workassignents', len(tasks))
    run_tasks(tasks, SYNC_QUEUE)
    run_tasks(skip_tasks, SYNC_QUEUE)

    if len(items) > 0:
        deferred.defer(_sync_all, last_sync, offset + len(items), _queue=SYNC_QUEUE)


def _update_one(gipod_id, skip_if_exists=False):
    m_key = WorkAssignment.create_key(WorkAssignment.TYPE, gipod_id)
    m = m_key.get()
    if m and skip_if_exists:
        return
    if not m:
        m = WorkAssignment(key=m_key)

    m.data = do_request('/workassignment/%s' % gipod_id)
    validate_and_clean_data(m.TYPE, m.uid, m.data)
    re_index_workassignment(m)


@returns()
@arguments(m_key=ndb.Key)
def re_index(m_key):
    m = m_key.get()
    re_index_workassignment(m)


@returns()
@arguments(workassignment=WorkAssignment)
def re_index_workassignment(workassignment):
    delete_docs(workassignment.search_keys)

    workassignment.visible = False
    workassignment.cleanup_date = None
    workassignment.search_keys = []

    now_ = datetime.utcnow()
    end_date = datetime.strptime(workassignment.data['endDateTime'], "%Y-%m-%dT%H:%M:%S")
    if end_date <= now_:
        workassignment.put()
        return []
    
    uid = workassignment.uid

    workassignment.visible = True
    workassignment.cleanup_date = end_date
    workassignment.search_keys.append(uid)
    workassignment.put()

    start_date = datetime.strptime(workassignment.data['startDateTime'], "%Y-%m-%dT%H:%M:%S")
    doc = {
        "location": {
            "lat": workassignment.data['location']['coordinate']['coordinates'][1],
            "lon": workassignment.data['location']['coordinate']['coordinates'][0]
        },
        "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
        "time_frame": {
            "gte" : start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "lte" : end_date.strftime("%Y-%m-%d %H:%M:%S")
        }
    }

    index_doc(uid, doc)


def re_index_all():
    run_job(re_index_query, [], re_index_worker, [])


def re_index_worker(m_key):
    re_index(m_key)


def re_index_query():
    return WorkAssignment.query()


def cleanup_timed_out_worker(m_key):
    re_index(m_key)


def cleanup_timed_out_query():
    qry = WorkAssignment.query()
    qry = qry.filter(WorkAssignment.cleanup_date != None)
    qry = qry.filter(WorkAssignment.cleanup_date < datetime.utcnow())
    qry = qry.order(WorkAssignment.cleanup_date, WorkAssignment.key)
    return qry


def cleanup_deleted_worker(m_key):
    uid = m_key.id()
    gipod_id = uid.split('-')[1]
    result = do_request_without_processing('/workassignment/%s' % gipod_id)
    if result.status_code == 200:
        return
    if result.status_code != 404:
        logging.warn('cleanup_deleted_worker failed for %s with status code %s', uid, result.status_code)
        return
    logging.debug('cleanup_deleted_worker deleted %s', uid)

    m = m_key.get()

    delete_docs(m.search_keys)

    m.cleanup_date = None
    m.search_keys = []
    m.visible = False
    m.put()


def cleanup_deleted_query():
    qry = WorkAssignment.query()
    qry = qry.filter(WorkAssignment.visible == True)
    return qry
