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

import mock
from oslo_messaging.rpc import dispatcher as rpc
import six

from senlin.common import exception
from senlin.common.i18n import _
from senlin.db import api as db_api
from senlin.engine.actions import base as action_mod
from senlin.engine import cluster as cluster_mod
from senlin.engine import dispatcher
from senlin.engine import environment
from senlin.engine import service
from senlin.tests.common import base
from senlin.tests.common import utils
from senlin.tests import fakes


class ClusterTest(base.SenlinTestCase):

    def setUp(self):
        super(ClusterTest, self).setUp()
        self.ctx = utils.dummy_context(tenant_id='cluster_test_tenant')
        self.eng = service.EngineService('host-a', 'topic-a')
        self.eng.init_tgm()

        self.eng.dispatcher = mock.Mock()

        env = environment.global_env()
        env.register_profile('TestProfile', fakes.TestProfile)
        env.register_policy('TestPolicy', fakes.TestPolicy)

        self.profile = self.eng.profile_create(
            self.ctx, 'p-test', 'TestProfile',
            spec={'INT': 10, 'STR': 'string'}, perm='1111')

        self.policy = self.eng.policy_create(
            self.ctx, 'policy_1', 'TestPolicy',
            spec={'KEY1': 'string'}, cooldown=60, level=50)

    def _verify_action(self, obj, action, name, target, cause, inputs=None):
        self.assertEqual(action, obj['action'])
        self.assertEqual(name, obj['name'])
        self.assertEqual(target, obj['target'])
        self.assertEqual(cause, obj['cause'])
        self.assertEqual(inputs, obj['inputs'])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_create_default(self, notify):
        result = self.eng.cluster_create(self.ctx, 'c-1', 0,
                                         self.profile['id'])
        self.assertIsNotNone(result)
        self.assertEqual('c-1', result['name'])
        self.assertEqual(0, result['size'])
        self.assertEqual(self.profile['id'], result['profile_id'])
        self.assertEqual(self.ctx.user, result['user'])
        self.assertEqual('cluster_test_tenant', result['project'])
        self.assertIsNone(result['parent'])
        self.assertIsNone(result['timeout'])
        self.assertIsNone(result['tags'])

        action_id = result['action']
        action = db_api.action_get(self.ctx, result['action'])
        self.assertIsNotNone(action)
        self._verify_action(action, 'CLUSTER_CREATE',
                            'cluster_create_%s' % result['id'][:8],
                            result['id'],
                            cause=action_mod.CAUSE_RPC)
        notify.assert_called_once_with(self.ctx,
                                       self.eng.dispatcher.NEW_ACTION,
                                       None, action_id=action_id)

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_create_with_timeout(self, notify):
        result = self.eng.cluster_create(self.ctx, 'c-1', 0,
                                         self.profile['id'],
                                         timeout=120)

        self.assertIsNotNone(result)
        self.assertEqual('c-1', result['name'])
        self.assertEqual(120, result['timeout'])

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_create,
                               self.ctx, 'c-1', 0,
                               self.profile['id'],
                               timeout='N/A')

        self.assertEqual(exception.InvalidParameter, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_create_with_size(self, notify):
        result = self.eng.cluster_create(self.ctx, 'c-1', 2,
                                         self.profile['id'])

        self.assertIsNotNone(result)
        self.assertEqual('c-1', result['name'])
        self.assertEqual(2, result['size'])

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_create,
                               self.ctx, 'c-1', 'Big',
                               self.profile['id'])

        self.assertEqual(exception.InvalidParameter, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_create_with_parent(self, notify):
        result = self.eng.cluster_create(self.ctx, 'c-1', 2,
                                         self.profile['id'],
                                         parent='fake id')

        self.assertIsNotNone(result)
        self.assertEqual('c-1', result['name'])
        self.assertEqual('fake id', result['parent'])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_create_with_tags(self, notify):
        result = self.eng.cluster_create(self.ctx, 'c-1', 2,
                                         self.profile['id'],
                                         tags={'k': 'v'})

        self.assertIsNotNone(result)
        self.assertEqual('c-1', result['name'])
        self.assertEqual({'k': 'v'}, result['tags'])

    def test_cluster_create_profile_not_found(self):
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_create,
                               self.ctx, 'c-1', 0, 'Bogus')
        self.assertEqual(exception.ProfileNotFound, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_create_with_profile_name_or_short_id(self, notify):
        result = self.eng.cluster_create(self.ctx, 'c-1', 0,
                                         self.profile['id'][:8])
        self.assertIsNotNone(result)
        self.assertEqual(self.profile['id'], result['profile_id'])

        self.eng.cluster_create(self.ctx, 'c-2', 0, self.profile['name'])
        self.assertIsNotNone(result)
        self.assertEqual(self.profile['id'], result['profile_id'])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_get(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0,
                                    self.profile['id'])

        for identity in [c['id'], c['id'][:6], 'c-1']:
            result = self.eng.cluster_get(self.ctx, identity)
            self.assertIsInstance(result, dict)
            self.assertEqual(c['id'], result['id'])

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_get, self.ctx, 'Bogus')
        self.assertEqual(exception.ClusterNotFound, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_list(self, notify):
        c1 = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        c2 = self.eng.cluster_create(self.ctx, 'c-2', 0, self.profile['id'])
        result = self.eng.cluster_list(self.ctx)
        self.assertIsInstance(result, list)
        names = [c['name'] for c in result]
        ids = [c['id'] for c in result]
        self.assertIn(c1['name'], names[0])
        self.assertIn(c2['name'], names[1])
        self.assertIn(c1['id'], ids[0])
        self.assertIn(c2['id'], ids[1])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_list_with_limit_marker(self, notify):
        c1 = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        c2 = self.eng.cluster_create(self.ctx, 'c-2', 0, self.profile['id'])
        result = self.eng.cluster_list(self.ctx, limit=0)

        self.assertEqual(0, len(result))
        result = self.eng.cluster_list(self.ctx, limit=1)
        self.assertEqual(1, len(result))
        result = self.eng.cluster_list(self.ctx, limit=2)
        self.assertEqual(2, len(result))
        result = self.eng.cluster_list(self.ctx, limit=3)
        self.assertEqual(2, len(result))

        result = self.eng.cluster_list(self.ctx, marker=c1['id'])
        self.assertEqual(1, len(result))
        result = self.eng.cluster_list(self.ctx, marker=c2['id'])
        self.assertEqual(0, len(result))

        self.eng.cluster_create(self.ctx, 'c-3', 0, self.profile['id'])

        result = self.eng.cluster_list(self.ctx, limit=1, marker=c1['id'])
        self.assertEqual(1, len(result))
        result = self.eng.cluster_list(self.ctx, limit=2, marker=c1['id'])
        self.assertEqual(2, len(result))

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_list_with_sort_keys(self, notify):
        c1 = self.eng.cluster_create(self.ctx, 'CC', 0, self.profile['id'])
        c2 = self.eng.cluster_create(self.ctx, 'BB', 0, self.profile['id'])

        # default by created_time
        result = self.eng.cluster_list(self.ctx)
        self.assertEqual(c1['id'], result[0]['id'])
        self.assertEqual(c2['id'], result[1]['id'])

        # use name for sorting
        result = self.eng.cluster_list(self.ctx, sort_keys=['name'])
        self.assertEqual(c2['id'], result[0]['id'])
        self.assertEqual(c1['id'], result[1]['id'])

        # unknown keys will be ignored
        result = self.eng.cluster_list(self.ctx, sort_keys=['duang'])
        self.assertIsNotNone(result)

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_list_with_sort_dir(self, notify):
        c1 = self.eng.cluster_create(self.ctx, 'BB', 0, self.profile['id'])
        c2 = self.eng.cluster_create(self.ctx, 'AA', 0, self.profile['id'])
        c3 = self.eng.cluster_create(self.ctx, 'CC', 0, self.profile['id'])

        # default by created_time, ascending
        result = self.eng.cluster_list(self.ctx)
        self.assertEqual(c1['id'], result[0]['id'])
        self.assertEqual(c2['id'], result[1]['id'])

        # sort by created_time, descending
        result = self.eng.cluster_list(self.ctx, sort_dir='desc')
        self.assertEqual(c3['id'], result[0]['id'])
        self.assertEqual(c2['id'], result[1]['id'])

        # use name for sorting, descending
        result = self.eng.cluster_list(self.ctx, sort_keys=['name'],
                                       sort_dir='desc')
        self.assertEqual(c3['id'], result[0]['id'])
        self.assertEqual(c1['id'], result[1]['id'])

        # use permission for sorting
        ex = self.assertRaises(ValueError,
                               self.eng.cluster_list, self.ctx,
                               sort_dir='Bogus')
        self.assertEqual("Unknown sort direction, must be "
                         "'desc' or 'asc'", six.text_type(ex))

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_list_show_deleted(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        result = self.eng.cluster_list(self.ctx)
        self.assertEqual(1, len(result))
        self.assertEqual(c['id'], result[0]['id'])

        db_api.cluster_delete(self.ctx, c['id'])

        result = self.eng.cluster_list(self.ctx)
        self.assertEqual(0, len(result))

        result = self.eng.cluster_list(self.ctx, show_deleted=True)
        self.assertEqual(1, len(result))
        self.assertEqual(c['id'], result[0]['id'])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_list_show_nested(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'],
                                    parent='other-cluster')
        result = self.eng.cluster_list(self.ctx)
        self.assertEqual(0, len(result))

        result = self.eng.cluster_list(self.ctx, show_nested=True)
        self.assertEqual(1, len(result))
        self.assertEqual(c['id'], result[0]['id'])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_list_with_filters(self, notify):
        self.eng.cluster_create(self.ctx, 'BB', 0, self.profile['id'])
        self.eng.cluster_create(self.ctx, 'AA', 0, self.profile['id'])
        self.eng.cluster_create(self.ctx, 'CC', 0, self.profile['id'])

        result = self.eng.cluster_list(self.ctx, filters={'name': 'BB'})
        self.assertEqual(1, len(result))
        self.assertEqual('BB', result[0]['name'])

        result = self.eng.cluster_list(self.ctx, filters={'name': 'DD'})
        self.assertEqual(0, len(result))

    def test_cluster_list_bad_param(self):
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_list, self.ctx, limit='no')
        self.assertEqual(exception.InvalidParameter, ex.exc_info[0])

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_list, self.ctx,
                               show_deleted='no')
        self.assertEqual(exception.InvalidParameter, ex.exc_info[0])

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_list, self.ctx,
                               show_nested='no')
        self.assertEqual(exception.InvalidParameter, ex.exc_info[0])

    def test_cluster_list_empty(self):
        result = self.eng.cluster_list(self.ctx)
        self.assertIsInstance(result, list)
        self.assertEqual(0, len(result))

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_find(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c['id']

        result = self.eng.cluster_find(self.ctx, cid)
        self.assertIsNotNone(result)

        # short id
        result = self.eng.cluster_find(self.ctx, cid[:5])
        self.assertIsNotNone(result)

        # name
        result = self.eng.cluster_find(self.ctx, 'c-1')
        self.assertIsNotNone(result)

        # others
        self.assertRaises(exception.ClusterNotFound,
                          self.eng.cluster_find, self.ctx, 'Bogus')

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_find_show_deleted(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c['id']
        db_api.cluster_delete(self.ctx, cid)

        for identity in [cid, cid[:6], 'c-1']:
            self.assertRaises(exception.ClusterNotFound,
                              self.eng.cluster_find, self.ctx, identity)

        # short id and name based finding does not support show_deleted
        for identity in [cid[:6], 'p-1']:
            self.assertRaises(exception.ClusterNotFound,
                              self.eng.cluster_find, self.ctx, identity)

        # ID based finding is okay with show_deleted
        result = self.eng.cluster_find(self.ctx, cid, show_deleted=True)
        self.assertIsNotNone(result)

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_simple_success(self, notify):
        c1 = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c1['id']

        # 1. update name
        self.eng.cluster_update(self.ctx, cid, name='c-2')
        c = self.eng.cluster_get(self.ctx, cid)
        self.assertEqual(cid, c['id'])
        self.assertEqual('c-2', c['name'])

        # 2. update parent
        p = self.eng.cluster_create(self.ctx, 'parent', 0, self.profile['id'])
        self.eng.cluster_update(self.ctx, cid, parent=p['id'])
        c = self.eng.cluster_get(self.ctx, cid)
        self.assertEqual(cid, c['id'])
        self.assertEqual(p['id'], c['parent'])

        # 3. update tags
        self.eng.cluster_update(self.ctx, cid, tags={'k': 'v'})
        c = self.eng.cluster_get(self.ctx, cid)
        self.assertEqual(cid, c['id'])
        self.assertEqual({'k': 'v'}, c['tags'])

        # 4. update timeout
        self.eng.cluster_update(self.ctx, cid, timeout=119)
        c = self.eng.cluster_get(self.ctx, cid)
        self.assertEqual(cid, c['id'])
        self.assertEqual(119, c['timeout'])

    def test_cluster_update_cluster_not_found(self):
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_update, self.ctx, 'Bogus')

        self.assertEqual(exception.ClusterNotFound, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_cluster_bad_status(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cluster = cluster_mod.Cluster.load(self.ctx, c['id'])
        cluster.set_status(self.ctx, cluster.DELETED, reason='test')

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_update, self.ctx, c['id'],
                               name='new name')

        self.assertEqual(exception.ClusterNotFound, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_parent_not_found(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_update, self.ctx, c['id'],
                               parent='Bogus')

        self.assertEqual(exception.ClusterNotFound, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_timeout_not_integer(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_update, self.ctx, c['id'],
                               timeout='Long')

        self.assertEqual(exception.InvalidParameter, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_cluster_status_error(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cluster = cluster_mod.Cluster.load(self.ctx, c['id'])
        cluster.set_status(self.ctx, cluster.ERROR, reason='test')

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_update, self.ctx, c['id'],
                               profile_id='good_profile')

        self.assertEqual(exception.NotSupported, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_update_to_same_profile(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        self.eng.cluster_update(self.ctx, c['id'],
                                profile_id=self.profile['id'])
        result = self.eng.cluster_get(self.ctx, c['id'])
        self.assertEqual(c['id'], result['id'])
        self.assertEqual(c['profile_id'], result['profile_id'])

        # notify is only called once, because the 'cluster_update' operation
        # was not causing any new action to be dispatched
        notify.assert_called_once()

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_update_to_diff_profile_type(self, notify):
        # Register a different profile
        env = environment.global_env()
        env.register_profile('DiffProfileType', fakes.TestProfile)
        new_profile = self.eng.profile_create(
            self.ctx, 'p-test', 'DiffProfileType',
            spec={'INT': 10, 'STR': 'string'}, perm='1111')

        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_update,
                               self.ctx, c['id'], profile_id=new_profile['id'])

        self.assertEqual(exception.ProfileTypeNotMatch, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_profile_not_found(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_update,
                               self.ctx, c['id'], profile_id='Bogus')

        self.assertEqual(exception.ProfileNotFound, ex.exc_info[0])

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_update_profile_normal(self, notify):
        new_profile = self.eng.profile_create(
            self.ctx, 'p-new', 'TestProfile',
            spec={'INT': 20, 'STR': 'string new'})

        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        self.eng.cluster_update(self.ctx, c['id'],
                                profile_id=new_profile['id'])

        # TODO(anyone): uncomment the following lines when cluster-update
        # is implemented
        # action_id = result['action']
        # action = self.eng.action_get(self.ctx, action_id)
        # self._verify_action(action, 'CLUSTER_UPDATE',
        #                     'cluster_update_%s' % c['id'][:8],
        #                     result['id'],
        #                     cause=action_mod.CAUSE_RPC)

        # notify.assert_called_once_with(self.ctx,
        #                                self.eng.dispatcher.NEW_ACTION,
        #                                None, action_id=action_id)

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_delete(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c['id']

        result = self.eng.cluster_delete(self.ctx, cid)
        self.assertIsNotNone(result)

        # verify action is fired
        action_id = result['action']
        action = self.eng.action_get(self.ctx, action_id)
        self._verify_action(action, 'CLUSTER_DELETE',
                            'cluster_delete_%s' % c['id'][:8],
                            c['id'],
                            cause=action_mod.CAUSE_RPC)

        expected_call = mock.call(self.ctx,
                                  self.eng.dispatcher.NEW_ACTION,
                                  None, action_id=mock.ANY)

        # two calls: one for create, the other for delete
        notify.assert_has_calls([expected_call] * 2)

    def test_cluster_delete_not_found(self):
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_delete, self.ctx, 'Bogus')

        self.assertEqual(exception.ClusterNotFound, ex.exc_info[0])
        self.assertEqual('The cluster (Bogus) could not be found.',
                         six.text_type(ex.exc_info[1]))

    def _prepare_nodes(self, ctx, count=3, profile_id=None, **kwargs):
        '''Prepare nodes for add or delete.'''
        nodes = []
        for i in range(count):
            values = {
                'name': 'test_node_name',
                'physical_id': 'fake-phy-id-%s' % (i + 1),
                'cluster_id': None,
                'profile_id': profile_id or self.profile['id'],
                'project': ctx.tenant_id,
                'index': i + 1,
                'role': None,
                'created_time': None,
                'updated_time': None,
                'deleted_time': None,
                'status': 'ACTIVE',
                'status_reason': 'create complete',
                'tags': {'foo': '123'},
                'data': {'key1': 'value1'},
            }
            values.update(kwargs)
            db_node = db_api.node_create(ctx, values)
            nodes.append(six.text_type(db_node.id))
        return nodes

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_add_nodes(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c['id']
        nodes = self._prepare_nodes(self.ctx)

        result = self.eng.cluster_add_nodes(self.ctx, cid, nodes)

        # verify action is fired
        action_id = result['action']
        action = self.eng.action_get(self.ctx, action_id)
        self._verify_action(action, 'CLUSTER_ADD_NODES',
                            'cluster_add_nodes_%s' % cid[:8],
                            cid, cause=action_mod.CAUSE_RPC,
                            inputs={'nodes': nodes})

        expected_call = mock.call(self.ctx,
                                  self.eng.dispatcher.NEW_ACTION,
                                  None, action_id=mock.ANY)

        # two calls: one for create, the other for adding nodes
        notify.assert_has_calls([expected_call] * 2)

    def test_cluster_add_nodes_cluster_not_found(self, notify):
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_add_nodes,
                               self.ctx, 'Bogus', ['n1', 'n2'])

        self.assertEqual(exception.ClusterNotFound, ex.exc_info[0])
        self.assertEqual('The cluster (Bogus) could not be found.',
                         six.text_type(ex.exc_info[1]))

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_add_nodes_empty_list(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c['id']

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_add_nodes,
                               self.ctx, cid, [])

        self.assertEqual(exception.SenlinBadRequest, ex.exc_info[0])
        self.assertEqual('The request is malformed: No nodes to add: []',
                         six.text_type(ex.exc_info[1]))

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_add_nodes_node_not_found(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c['id']

        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_add_nodes,
                               self.ctx, cid, ['Bogus'])

        self.assertEqual(exception.SenlinBadRequest, ex.exc_info[0])
        self.assertEqual("The request is malformed: Nodes not found: "
                         "['Bogus']", six.text_type(ex.exc_info[1]))

    @mock.patch.object(dispatcher, 'notify')
    def test_cluster_add_nodes_node_not_active(self, notify):
        c = self.eng.cluster_create(self.ctx, 'c-1', 0, self.profile['id'])
        cid = c['id']
        nodes = self._prepare_nodes(self.ctx, count=1, status='ERROR')
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.cluster_add_nodes,
                               self.ctx, cid, nodes)

        self.assertEqual(exception.SenlinBadRequest, ex.exc_info[0])
        msg = _("Nodes are not ACTIVE: %s") % nodes
        self.assertEqual(_("The request is malformed: %(msg)s") % {'msg': msg},
                         six.text_type(ex.exc_info[1]))
