# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

'''
Unit Tests for senlin.rpc.client
'''


import copy
import mock
from oslo_messaging._drivers import common as rpc_common

from senlin.common import exception
from senlin.common import messaging
from senlin.rpc import client as rpc_client
from senlin.tests.common import base
from senlin.tests.common import utils


class EngineRpcAPITestCase(base.SenlinTestCase):

    def setUp(self):
        messaging.setup("fake://", optional=True)
        self.addCleanup(messaging.cleanup)
        self.context = utils.dummy_context()

        # self.stubs = stubout.StubOutForTesting()
        self.rpcapi = rpc_client.EngineClient()
        super(EngineRpcAPITestCase, self).setUp()

    def _to_remote_error(self, error):
        '''Converts the given exception to one with the _Remote suffix.'''
        exc_info = (type(error), error, None)
        serialized = rpc_common.serialize_remote_exception(exc_info)
        remote_error = rpc_common.deserialize_remote_exception(
            serialized, ["senlin.common.exception"])
        return remote_error

    def test_local_error_name(self):
        ex = exception.NotFound()
        self.assertEqual('NotFound', self.rpcapi.local_error_name(ex))

        exr = self._to_remote_error(ex)
        self.assertEqual('NotFound_Remote', exr.__class__.__name__)
        self.assertEqual('NotFound', self.rpcapi.local_error_name(exr))

    def test_ignore_error_named(self):
        ex = exception.NotFound()
        exr = self._to_remote_error(ex)

        self.rpcapi.ignore_error_named(ex, 'NotFound')
        self.rpcapi.ignore_error_named(exr, 'NotFound')
        self.assertRaises(exception.NotFound,
                          self.rpcapi.ignore_error_named, ex, 'NotSupported')
        self.assertRaises(exception.NotFound,
                          self.rpcapi.ignore_error_named, exr, 'NotSupported')

    def _test_engine_api(self, method, rpc_method, **kwargs):
        ctxt = utils.dummy_context()
        expected_retval = 'foo' if method == 'call' else None

        kwargs.pop('version', None)

        if 'expected_message' in kwargs:
            expected_message = kwargs['expected_message']
            del kwargs['expected_message']
        else:
            expected_message = self.rpcapi.make_msg(method, **kwargs)

        cast_and_call = [
            'profile_delete',
            'policy_delete',
            'cluster_delete',
            'node_delete'
        ]

        if rpc_method == 'call' and method in cast_and_call:
            kwargs['cast'] = False

        mock_rpc_method = self.patchobject(self.rpcapi, rpc_method,
                                           return_value=expected_retval)

        retval = getattr(self.rpcapi, method)(ctxt, **kwargs)

        self.assertEqual(expected_retval, retval)
        expected_args = [ctxt, expected_message, mock.ANY]
        actual_args, _ = mock_rpc_method.call_args
        for expected_arg, actual_arg in zip(expected_args, actual_args):
            self.assertEqual(expected_arg, actual_arg)

    def test_profile_type_list(self):
        self._test_engine_api('profile_type_list', 'call')

    def test_profile_type_schema(self):
        self._test_engine_api('profile_type_schema', 'call',
                              type_name='a-profile-type')

    def test_profile_list(self):
        default_args = {
            'limit': mock.ANY,
            'marker': mock.ANY,
            'sort_keys': mock.ANY,
            'sort_dir': mock.ANY,
            'filters': mock.ANY,
            'show_deleted': mock.ANY,
        }
        self._test_engine_api('profile_list', 'call', **default_args)

    def test_profile_create(self):
        default_args = {
            'name': mock.ANY,
            'type': mock.ANY,
            'spec': mock.ANY,
            'perm': mock.ANY,
            'tags': mock.ANY,
        }
        self._test_engine_api('profile_create', 'call', **default_args)

    def test_profile_get(self):
        self._test_engine_api('profile_get', 'call', identity='a-profile')

    def test_profile_update(self):
        default_args = {
            'profile_id': 'aaaa-bbbb-cccc',
            'name': mock.ANY,
            'spec': mock.ANY,
            'permission': mock.ANY,
            'tags': mock.ANY,
        }
        self._test_engine_api('profile_update', 'call', **default_args)

    def test_profile_delete_cast(self):
        self._test_engine_api('profile_delete', 'cast', identity='a-profile')

    def test_profile_delete_call(self):
        self._test_engine_api('profile_delete', 'call', identity='a-profile')

    def test_policy_type_list(self):
        self._test_engine_api('policy_type_list', 'call')

    def test_policy_type_schema(self):
        self._test_engine_api('policy_type_schema', 'call',
                              type_name='a-profile-type')

    def test_policy_list(self):
        default_args = {
            'limit': mock.ANY,
            'marker': mock.ANY,
            'sort_keys': mock.ANY,
            'sort_dir': mock.ANY,
            'filters': mock.ANY,
            'show_deleted': mock.ANY,
        }
        self._test_engine_api('policy_list', 'call', **default_args)

    def test_policy_create(self):
        default_args = {
            'name': mock.ANY,
            'type': mock.ANY,
            'spec': mock.ANY,
            'level': mock.ANY,
            'cooldown': mock.ANY,
        }
        self._test_engine_api('policy_create', 'call', **default_args)

    def test_policy_get(self):
        self._test_engine_api('policy_get', 'call', identity='a-policy')

    def test_policy_update(self):
        default_args = {
            'identity': 'aaaa-bbbb-cccc',
            'name': mock.ANY,
            'level': mock.ANY,
            'cooldown': mock.ANY,
        }
        self._test_engine_api('policy_update', 'call', **default_args)

    def test_policy_delete_cast(self):
        self._test_engine_api('policy_delete', 'cast', identity='a-policy')

    def test_policy_delete_call(self):
        self._test_engine_api('policy_delete', 'call', identity='a-policy')

    def test_cluster_list(self):
        default_args = {
            'limit': mock.ANY,
            'marker': mock.ANY,
            'sort_keys': mock.ANY,
            'sort_dir': mock.ANY,
            'filters': mock.ANY,
            'tenant_safe': mock.ANY,
            'show_deleted': mock.ANY,
            'show_nested': mock.ANY,
        }
        self._test_engine_api('cluster_list', 'call', **default_args)

    def test_cluster_create(self):
        kwargs = {
            'name': 'mycluster',
            'size': 0,
            'profile_id': 'aaaa-bbbb-cccc',
            'parent': None,
            'tags': None,
            'timeout': None
        }

        self._test_engine_api('cluster_create', 'call', **kwargs)

    def test_cluster_get(self):
        self._test_engine_api('cluster_get', 'call', identity='a-cluster')

    def test_cluster_add_nodes(self):
        self._test_engine_api('cluster_add_nodes', 'call',
                              identity='a-cluster',
                              nodes=['node1', 'node2'])

    def test_cluster_del_nodes(self):
        self._test_engine_api('cluster_del_nodes', 'call',
                              identity='a-cluster',
                              nodes=['node3', 'node4'])

    def test_cluster_scale_out(self):
        self._test_engine_api('cluster_scale_out', 'call',
                              identity='a-cluster',
                              count=1)

    def test_cluster_scale_in(self):
        self._test_engine_api('cluster_scale_in', 'call',
                              identity='a-cluster',
                              count=1)

    def test_cluster_update(self):
        kwargs = {
            'identity': 'a-cluster',
            'name': 'new-name',
            'profile_id': 'new_profile',
            'parent': 'another-cluster',
            'tags': {'key': 'value'},
            'timeout': 120
        }
        self._test_engine_api('cluster_update', 'call', **kwargs)

    def test_cluster_delete_cast(self):
        self._test_engine_api('cluster_delete', 'cast', identity='a-cluster')

    def test_cluster_delete_call(self):
        self._test_engine_api('cluster_delete', 'call', identity='a-cluster')

    def test_node_list(self):
        default_args = {
            'cluster_id': mock.ANY,
            'show_deleted': mock.ANY,
            'limit': mock.ANY,
            'marker': mock.ANY,
            'sort_keys': mock.ANY,
            'sort_dir': mock.ANY,
            'filters': mock.ANY,
            'tenant_safe': mock.ANY,
        }
        self._test_engine_api('node_list', 'call', **default_args)

    def test_node_create(self):
        kwargs = {
            'name': 'mynode',
            'profile_id': 'aaaa-bbbb-cccc',
            'cluster_id': 'xxxx-yyyy-zzzz',
            'role': None,
            'tags': None
        }

        self._test_engine_api('node_create', 'call', **kwargs)

    def test_node_get(self):
        self._test_engine_api('node_get', 'call', identity='a-node')

    def test_node_join(self):
        self._test_engine_api('node_join', 'call',
                              identity='a-node',
                              cluster_id='another-cluster')

    def test_node_leave(self):
        self._test_engine_api('node_leave', 'call', identity='a-node')

    def test_node_update(self):
        kwargs = {
            'identity': 'a-cluster',
            'name': 'new-name',
            'profile_id': 'new_profile',
            'role': 'master',
            'tags': {'key': 'value'}
        }
        self._test_engine_api('node_update', 'call', **kwargs)

    def test_node_delete_cast(self):
        self._test_engine_api('node_delete', 'cast', identity='a-node',
                              force=False)

    def test_node_delete_call(self):
        self._test_engine_api('node_delete', 'call', identity='a-node',
                              force=False)

    def test_action_list(self):
        default_args = {
            'filters': mock.ANY,
            'limit': mock.ANY,
            'marker': mock.ANY,
            'sort_keys': mock.ANY,
            'sort_dir': mock.ANY,
            'show_deleted': mock.ANY,
        }
        self._test_engine_api('action_list', 'call', **default_args)

    def test_cluster_policy_list(self):
        kwargs = {
            'cluster_id': 'a-cluster',
            'filters': mock.ANY,
            'sort_keys': mock.ANY,
            'sort_dir': mock.ANY,
        }
        call_kwargs = copy.deepcopy(kwargs)
        call_kwargs['identity'] = 'a-cluster'
        del call_kwargs['cluster_id']
        expected_message = self.rpcapi.make_msg('cluster_policy_list',
                                                **call_kwargs)
        kwargs['expected_message'] = expected_message
        self._test_engine_api('cluster_policy_list', 'call', **kwargs)

    def test_cluster_policy_get(self):
        kwargs = {
            'cluster_id': 'a-cluster',
            'policy_id': 'a-policy',
        }

        call_kwargs = {
            'identity': 'a-cluster',
            'policy_id': 'a-policy',
        }
        expected_message = self.rpcapi.make_msg('cluster_policy_get',
                                                **call_kwargs)
        kwargs['expected_message'] = expected_message
        self._test_engine_api('cluster_policy_get', 'call', **kwargs)

    def test_cluster_policy_update(self):
        kwargs = {
            'cluster_id': 'a-cluster',
            'policy_id': 'a-policy',
            'priority': 77,
            'level': 88,
            'cooldown': 120,
            'enabled': True
        }

        call_kwargs = copy.deepcopy(kwargs)
        call_kwargs['identity'] = 'a-cluster'
        call_kwargs['policy'] = 'a-policy'
        del call_kwargs['cluster_id']
        del call_kwargs['policy_id']
        expected_message = self.rpcapi.make_msg('cluster_policy_update',
                                                **call_kwargs)
        kwargs['expected_message'] = expected_message
        self._test_engine_api('cluster_policy_update', 'call', **kwargs)

    def test_action_create(self):
        kwargs = {
            'name': 'myaction',
            'target': 'aaaa-bbbb-cccc',
            'action': 'this is a script',
            'params': None,
        }

        self._test_engine_api('action_create', 'call', **kwargs)

    def test_action_get(self):
        self._test_engine_api('action_get', 'call', identity='an-action')

    def test_event_list(self):
        default_args = {
            'filters': mock.ANY,
            'limit': mock.ANY,
            'marker': mock.ANY,
            'sort_keys': mock.ANY,
            'sort_dir': mock.ANY,
            'tenant_safe': mock.ANY,
            'show_deleted': mock.ANY,
        }
        self._test_engine_api('event_list', 'call', **default_args)

    def test_get_revision(self):
        self._test_engine_api('get_revision', 'call')
