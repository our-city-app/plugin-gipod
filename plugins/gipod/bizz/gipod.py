# -*- coding: utf-8 -*-
# Copyright 2020 Green Valley NV
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

from dateutil.parser import parse as parse_datetime
from dateutil.relativedelta import relativedelta
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import ndb, deferred
from typing import Type, Union, Tuple, List, Iterable

from framework.bizz.job import run_job, MODE_BATCH
from framework.consts import HIGH_LOAD_CONTROLLER_QUEUE
from framework.utils import chunks
from framework.utils.cloud_tasks import create_task, run_tasks, schedule_tasks
from mcfw.consts import DEBUG
from mcfw.rpc import arguments
from plugins.gipod.bizz import do_request, validate_and_clean_data, do_request_without_processing
from plugins.gipod.bizz.elasticsearch import delete_docs, index_doc_operations, delete_doc_operations, \
    execute_bulk_request
from plugins.gipod.models import Manifestation, SyncSettings, WorkAssignment
from plugins.gipod.plugin_consts import SYNC_QUEUE


mapping = {
    Manifestation.TYPE: {
        'list': '/manifestation',
        'detail': '/manifestation/%s',
        'class': Manifestation,
    },
    WorkAssignment.TYPE: {
        'list': '/workassignment',
        'detail': '/workassignment/%s',
        'class': WorkAssignment,
    }
}


def sync():
    key = SyncSettings.create_key()
    settings = key.get()
    if not settings:
        if DEBUG:
            settings = SyncSettings(key=key, synced_until=datetime(2000, 1, 1))
        else:
            return
    last_sync = settings.synced_until

    tasks = [create_task(_sync_all, Manifestation.TYPE, last_sync, 0),
             create_task(_sync_all, WorkAssignment.TYPE, last_sync, 0)]
    run_tasks(tasks)

    settings.synced_until = datetime.now()
    settings.put()


def cleanup_timed_out():
    current_date = datetime.utcnow()
    run_job(cleanup_timed_out_query, [Manifestation, current_date], re_index, [], mode=MODE_BATCH)
    run_job(cleanup_timed_out_query, [WorkAssignment, current_date], re_index, [], mode=MODE_BATCH)


def fetch_iter(qry, keys_only=True):
    # type: (ndb.Query, ndb.QueryOptions) -> Iterable[ndb.Key]
    cursor = None
    has_more = True
    while has_more:
        models, cursor, has_more = qry.fetch_page(datastore_rpc.BaseConnection.MAX_GET_KEYS, start_cursor=cursor,
                                                  keys_only=keys_only)
        for model in models:
            yield model


def cleanup_deleted():
    # Note: items might still be available using the /<type>/<id> endpoint,
    # but since it's not returned by the list result, delete them anyway since they probably
    # cache those detail results for a few days.
    # TODO might wanna use this method to create / update new items too
    for type in (Manifestation.TYPE, WorkAssignment.TYPE):
        end_date = datetime.now() + (relativedelta(days=1) if DEBUG else relativedelta(months=12))
        m = mapping[type]
        url = m['list']
        cls = m['class']
        per_page = 2000
        params = {'limit': '%s' % per_page, 'enddate': end_date.strftime('%Y-%m-%d')}
        gipod_ids = set()
        offset = 0
        while True:
            items = do_request(url, params)
            if not items:
                break
            offset += per_page
            params['offset'] = '%d' % offset
            for item in items:
                gipod_ids.add(cls.create_key(type, item['gipodId']).id())
        # Note: this api is not great and returns different results when using 'offset'
        # Not using offset causes memory usage to skyrocket so we can't do that
        logging.debug('Found %d %s items on gipod', len(gipod_ids), cls._get_kind())
        our_item_keys = {key for key in fetch_iter(cls.list())}
        to_delete = []
        for our_key in our_item_keys:
            if our_key.id() not in gipod_ids:
                to_delete.append(our_key)
        if to_delete:
            logging.debug('Marking %s %s as deleted', len(to_delete), cls._get_kind())
            tasks = []
            for keys_chunk in chunks(to_delete, 50):
                tasks.append(create_task(cleanup_deleted_worker, keys_chunk))
            schedule_tasks(tasks, SYNC_QUEUE)


def _sync_all(item_type, last_sync, offset):
    # type: (str, datetime, int) -> None
    end_date = datetime.now() + (relativedelta(days=1) if DEBUG else relativedelta(months=12))
    params = {
        'enddate': end_date.strftime('%Y-%m-%d'),
        'limit': '1000',
        'offset': '%s' % offset
    }

    tasks = []
    url = mapping[item_type]['list']
    items = do_request(url, params)
    for item in items:
        if last_sync:
            d = parse_datetime(item['latestUpdate'])
            if last_sync > d:
                tasks.append(create_task(_update_one, item_type, str(item['gipodId']), skip_if_exists=True))
                continue

        tasks.append(create_task(_update_one, item_type, str(item['gipodId'])))

    run_tasks(tasks, SYNC_QUEUE)

    if len(items) > 0:
        deferred.defer(_sync_all, item_type, last_sync, offset + len(items), _queue=HIGH_LOAD_CONTROLLER_QUEUE)


def _update_one(item_type, gipod_id, skip_if_exists=False):
    item = mapping[item_type]
    clazz = item['class']
    key = clazz.create_key(clazz.TYPE, gipod_id)
    model = key.get()
    if model and skip_if_exists:
        return
    if not model:
        model = clazz(key=key)

    model.data = do_request(item['detail'] % gipod_id)
    validate_and_clean_data(model.TYPE, model.uid, model.data)
    updated_model, es_operations = re_index_model(model)
    updated_model.put()
    execute_bulk_request(es_operations)


def re_index(keys):
    models = ndb.get_multi(keys)
    to_put = []
    operations = []
    for model in models:
        updated_model, es_operations = re_index_model(model)
        to_put.append(updated_model)
        operations.extend(es_operations)
    ndb.put_multi(to_put)
    execute_bulk_request(operations)


@arguments(item=(WorkAssignment, Manifestation))
def re_index_model(item):
    # type: (Union[WorkAssignment, Manifestation]) -> Tuple[Union[WorkAssignment, Manifestation], Iterable[dict]]
    item.cleanup_date = None
    operations = None
    now_ = datetime.utcnow()

    if isinstance(item, Manifestation):
        periods = []
        for period in item.data['periods']:
            start_date = parse_datetime(period['startDateTime'])
            end_date = parse_datetime(period['endDateTime'])
            if end_date <= now_:
                continue
            if not item.cleanup_date or item.cleanup_date > end_date:
                item.cleanup_date = end_date
            periods.append((start_date, end_date))
        if periods:
            operations = _index_item(item, periods)
    elif isinstance(item, WorkAssignment):
        start_date = parse_datetime(item.data['startDateTime'])
        end_date = parse_datetime(item.data['endDateTime'])
        item.cleanup_date = end_date
        operations = _index_item(item, [(start_date, end_date)])

    if not operations:
        operations = delete_doc_operations(item.uid)
    return item, operations


def _index_item(item, periods):
    # type: (Union[WorkAssignment, Manifestation], List[Tuple[datetime, datetime]]) -> dict
    time_frames = [{'gte': start_date.isoformat() + 'Z', 'lte': end_date.isoformat() + 'Z'}
                   for start_date, end_date in periods]
    data = item.data
    doc = {
        'location': {
            'lat': data['location']['coordinate']['coordinates'][1],
            'lon': data['location']['coordinate']['coordinates'][0]
        },
        'start_date': time_frames[0]['gte'],
        'end_date': time_frames[0]['lte'],
        'time_frames': time_frames,
    }
    return index_doc_operations(item.uid, doc)


def re_index_all():
    run_job(re_index_query, [Manifestation], re_index, [], mode=MODE_BATCH)
    run_job(re_index_query, [WorkAssignment], re_index, [], mode=MODE_BATCH)


def re_index_query(clazz):
    # type: (Type[Union[Manifestation, WorkAssignment]]) -> ndb.Query
    return clazz.query()


def cleanup_timed_out_query(clazz, current_date):
    # type: (Type[Union[Manifestation, WorkAssignment]], datetime) -> ndb.Query
    return clazz.list_timed_out(current_date)


def cleanup_deleted_worker(keys):
    to_delete = []
    # Gipod api does always not return the same results when doing the same query twice.
    # For this reason we doublecheck if an item is deleted or not by fetching its details.
    for key in keys:
        type_, gipod_id = key.id().split('-')
        item = mapping[type_]
        result = do_request_without_processing(item['detail'] % gipod_id)
        if result.status_code == 404:
            to_delete.append(key)
    logging.debug('Removing %d/%d items', len(to_delete), len(keys))
    if to_delete:
        delete_docs([key.id() for key in to_delete])
        ndb.delete_multi(to_delete)
