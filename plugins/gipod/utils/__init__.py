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

from framework.utils import azzert
from mcfw.rpc import returns, arguments


@returns(tuple)
@arguments(app_user_email=unicode)
def get_app_user_tuple_by_email(app_user_email):
    azzert('/' not in app_user_email, "app_user_email should not contain /")
    if ':' in app_user_email:
        human_user_email, app_id = app_user_email.split(':')
    else:
        APP_ID_ROGERTHAT = u"rogerthat"
        human_user_email, app_id = app_user_email, APP_ID_ROGERTHAT
    return human_user_email, app_id


@returns(unicode)
@arguments(user_id=unicode)
def get_app_id_from_user_id(user_id):
    return get_app_user_tuple_by_email(user_id)[1]
