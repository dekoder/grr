#!/usr/bin/env python
"""This modules contains regression tests for clients API handlers."""
from __future__ import unicode_literals


from builtins import range  # pylint: disable=redefined-builtin
import psutil

from grr_response_core.lib import flags
from grr_response_core.lib import rdfvalue

from grr_response_core.lib import utils
from grr_response_core.lib.rdfvalues import client as rdf_client
from grr_response_core.lib.rdfvalues import client_network as rdf_client_network
from grr_response_core.lib.rdfvalues import client_stats as rdf_client_stats
from grr_response_server import aff4
from grr_response_server import data_store
from grr_response_server import flow
from grr_response_server import queue_manager
from grr_response_server.aff4_objects import aff4_grr
from grr_response_server.aff4_objects import stats as aff4_stats
from grr_response_server.flows.general import processes

from grr_response_server.gui import api_regression_test_lib
from grr_response_server.gui.api_plugins import client as client_plugin
from grr.test_lib import client_test_lib
from grr.test_lib import flow_test_lib
from grr.test_lib import hunt_test_lib
from grr.test_lib import test_lib


class ApiSearchClientsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):

  api_method = "SearchClients"
  handler = client_plugin.ApiSearchClientsHandler

  def Run(self):
    # Fix the time to avoid regressions.
    with test_lib.FakeTime(42):
      if data_store.RelationalDBReadEnabled():
        client_obj = self.SetupTestClientObject(0)
        client_id = client_obj.client_id
      else:
        client_urn = self.SetupClient(0, add_cert=False)
        client_id = client_urn.Basename()

      self.Check(
          "SearchClients",
          args=client_plugin.ApiSearchClientsArgs(query=client_id))


class ApiGetClientHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):

  api_method = "GetClient"
  handler = client_plugin.ApiGetClientHandler

  def Run(self):
    # Fix the time to avoid regressions.
    with test_lib.FakeTime(42):
      if data_store.RelationalDBReadEnabled():
        client_obj = self.SetupTestClientObject(
            0, memory_size=4294967296, add_cert=False)
        client_id = client_obj.client_id
      else:
        client_urn = self.SetupClient(0, memory_size=4294967296, add_cert=False)
        client_id = client_urn.Basename()

    self.Check(
        "GetClient", args=client_plugin.ApiGetClientArgs(client_id=client_id))


class ApiGetClientVersionsRegressionTestMixin(object):

  api_method = "GetClientVersions"
  handler = client_plugin.ApiGetClientVersionsHandler

  def _SetupTestClient(self):

    if data_store.RelationalDBReadEnabled():

      with test_lib.FakeTime(42):
        client_obj = self.SetupTestClientObject(
            0, memory_size=4294967296, add_cert=False)
        client_id = client_obj.client_id

      with test_lib.FakeTime(45):
        self.SetupTestClientObject(
            0,
            fqdn="some-other-hostname.org",
            memory_size=4294967296,
            add_cert=False)

    else:  # We need AFF4 data.

      with test_lib.FakeTime(42):
        client_urn = self.SetupClient(0, memory_size=4294967296, add_cert=False)
        client_id = client_urn.Basename()

      with test_lib.FakeTime(45):
        with aff4.FACTORY.Open(
            client_urn, mode="rw", token=self.token) as grr_client:
          grr_client.Set(grr_client.Schema.HOSTNAME("some-other-hostname.org"))
          grr_client.Set(grr_client.Schema.FQDN("some-other-hostname.org"))
          kb = grr_client.Get(grr_client.Schema.KNOWLEDGE_BASE)
          kb.fqdn = "some-other-hostname.org"
          grr_client.Set(grr_client.Schema.KNOWLEDGE_BASE(kb))

    return client_id

  def Run(self):
    client_id = self._SetupTestClient()

    with test_lib.FakeTime(47):
      self.Check(
          "GetClientVersions",
          args=client_plugin.ApiGetClientVersionsArgs(
              client_id=client_id, mode=self.mode))
      self.Check(
          "GetClientVersions",
          args=client_plugin.ApiGetClientVersionsArgs(
              client_id=client_id,
              end=rdfvalue.RDFDatetime.FromSecondsSinceEpoch(44),
              mode=self.mode))
      self.Check(
          "GetClientVersions",
          args=client_plugin.ApiGetClientVersionsArgs(
              client_id=client_id,
              start=rdfvalue.RDFDatetime.FromSecondsSinceEpoch(44),
              end=rdfvalue.RDFDatetime.FromSecondsSinceEpoch(46),
              mode=self.mode))


class ApiGetClientVersionsRegressionTest(
    ApiGetClientVersionsRegressionTestMixin,
    api_regression_test_lib.ApiRegressionTest,
):

  mode = "FULL"


class ApiGetClientVersionsRegressionTestAFF4(
    ApiGetClientVersionsRegressionTestMixin,
    api_regression_test_lib.ApiRegressionTest,
):
  mode = "DIFF"

  # Disable the relational DB for this class, the functionality is not needed.
  aff4_only_test = True


class ApiGetLastClientIPAddressHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):

  api_method = "GetLastClientIPAddress"
  handler = client_plugin.ApiGetLastClientIPAddressHandler

  def Run(self):
    # Fix the time to avoid regressions.
    with test_lib.FakeTime(42):
      if data_store.RelationalDBReadEnabled():
        client_obj = self.SetupTestClientObject(0)
        client_id = client_obj.client_id

        ip = rdf_client_network.NetworkAddress(
            human_readable_address="192.168.100.42",
            address_type=rdf_client_network.NetworkAddress.Family.INET)
        data_store.REL_DB.WriteClientMetadata(client_id, last_ip=ip)
      else:
        client_urn = self.SetupClient(0)
        client_id = client_urn.Basename()

        with aff4.FACTORY.Open(
            client_id, mode="rw", token=self.token) as grr_client:
          grr_client.Set(grr_client.Schema.CLIENT_IP("192.168.100.42"))

    self.Check(
        "GetLastClientIPAddress",
        args=client_plugin.ApiGetLastClientIPAddressArgs(client_id=client_id))


class ApiListClientsLabelsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):

  api_method = "ListClientsLabels"
  handler = client_plugin.ApiListClientsLabelsHandler

  def Run(self):
    # Fix the time to avoid regressions.
    with test_lib.FakeTime(42):
      client_ids = self.SetupClients(2)

      self.AddClientLabel(client_ids[0], self.token.username, u"foo")
      self.AddClientLabel(client_ids[0], self.token.username, u"bar")

    self.Check("ListClientsLabels")


class ApiListKbFieldsHandlerTest(api_regression_test_lib.ApiRegressionTest):

  api_method = "ListKbFields"
  handler = client_plugin.ApiListKbFieldsHandler

  def Run(self):
    self.Check("ListKbFields")


class ApiListClientCrashesHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest,
    hunt_test_lib.StandardHuntTestMixin):

  api_method = "ListClientCrashes"
  handler = client_plugin.ApiListClientCrashesHandler

  def Run(self):
    if data_store.RelationalDBReadEnabled():
      client = self.SetupTestClientObject(0)
      client_id = client.client_id
      client_ids = [rdf_client.ClientURN(client_id)]
    else:
      client_ids = self.SetupClients(1)
      client_id = client_ids[0].Basename()
    client_mock = flow_test_lib.CrashClientMock(
        rdf_client.ClientURN(client_id), self.token)

    with test_lib.FakeTime(42):
      with self.CreateHunt(description="the hunt") as hunt_obj:
        hunt_obj.Run()

    with test_lib.FakeTime(45):
      self.AssignTasksToClients(client_ids)
      hunt_test_lib.TestHuntHelperWithMultipleMocks({
          client_id: client_mock
      }, False, self.token)

    crashes = aff4_grr.VFSGRRClient.CrashCollectionForCID(
        rdf_client.ClientURN(client_id))
    crash = list(crashes)[0]
    session_id = crash.session_id.Basename()
    replace = {hunt_obj.urn.Basename(): "H:123456", session_id: "H:11223344"}

    self.Check(
        "ListClientCrashes",
        args=client_plugin.ApiListClientCrashesArgs(client_id=client_id),
        replace=replace)
    self.Check(
        "ListClientCrashes",
        args=client_plugin.ApiListClientCrashesArgs(
            client_id=client_id, count=1),
        replace=replace)
    self.Check(
        "ListClientCrashes",
        args=client_plugin.ApiListClientCrashesArgs(
            client_id=client_id, offset=1, count=1),
        replace=replace)


class ApiListClientActionRequestsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest,
    hunt_test_lib.StandardHuntTestMixin):

  api_method = "ListClientActionRequests"
  handler = client_plugin.ApiListClientActionRequestsHandler

  def Run(self):
    client_id = self.SetupClient(0)

    replace = {}
    with test_lib.FakeTime(42):
      flow_urn = flow.StartAFF4Flow(
          client_id=client_id,
          flow_name=processes.ListProcesses.__name__,
          token=self.token)
      replace[flow_urn.Basename()] = "F:123456"

      test_process = client_test_lib.MockWindowsProcess(name="test_process")
      with utils.Stubber(psutil, "Process", lambda: test_process):
        # Here we emulate a mock client with no actions (None) that
        # should produce an error.
        mock = flow_test_lib.MockClient(client_id, None, token=self.token)
        while mock.Next():
          pass

    manager = queue_manager.QueueManager(token=self.token)
    requests_responses = manager.FetchRequestsAndResponses(flow_urn)
    for request, responses in requests_responses:
      replace[str(request.request.task_id)] = "42"
      for response in responses:
        replace[str(response.task_id)] = "43"

    self.Check(
        "ListClientActionRequests",
        args=client_plugin.ApiListClientActionRequestsArgs(
            client_id=client_id.Basename()),
        replace=replace)
    self.Check(
        "ListClientActionRequests",
        args=client_plugin.ApiListClientActionRequestsArgs(
            client_id=client_id.Basename(), fetch_responses=True),
        replace=replace)


class ApiGetClientLoadStatsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):

  api_method = "GetClientLoadStats"
  handler = client_plugin.ApiGetClientLoadStatsHandler

  def FillClientStats(self, client_id):
    with aff4.FACTORY.Create(
        client_id.Add("stats"),
        aff4_type=aff4_stats.ClientStats,
        token=self.token,
        mode="rw") as stats_fd:

      for i in range(6):
        with test_lib.FakeTime((i + 1) * 10):
          timestamp = int((i + 1) * 10 * 1e6)
          st = rdf_client_stats.ClientStats()

          sample = rdf_client_stats.CpuSample(
              timestamp=timestamp,
              user_cpu_time=10 + i,
              system_cpu_time=20 + i,
              cpu_percent=10 + i)
          st.cpu_samples.Append(sample)

          sample = rdf_client_stats.IOSample(
              timestamp=timestamp, read_bytes=10 + i, write_bytes=10 + i * 2)
          st.io_samples.Append(sample)

          stats_fd.AddAttribute(stats_fd.Schema.STATS(st))

  def Run(self):
    client_id = self.SetupClient(0)
    self.FillClientStats(client_id)

    self.Check(
        "GetClientLoadStats",
        args=client_plugin.ApiGetClientLoadStatsArgs(
            client_id=client_id.Basename(),
            metric="CPU_PERCENT",
            start=rdfvalue.RDFDatetime.FromSecondsSinceEpoch(10),
            end=rdfvalue.RDFDatetime.FromSecondsSinceEpoch(21)))
    self.Check(
        "GetClientLoadStats",
        args=client_plugin.ApiGetClientLoadStatsArgs(
            client_id=client_id.Basename(),
            metric="IO_WRITE_BYTES",
            start=rdfvalue.RDFDatetime.FromSecondsSinceEpoch(10),
            end=rdfvalue.RDFDatetime.FromSecondsSinceEpoch(21)))


def main(argv):
  api_regression_test_lib.main(argv)


if __name__ == "__main__":
  flags.StartMain(main)
