# Copyright 2015 ClusterHQ Inc.  See LICENSE file for details.
"""
Create Dataset operation tests for the control service benchmarks.
"""
from uuid import uuid4

from ipaddr import IPAddress
from zope.interface.verify import verifyClass

from twisted.internet.task import Clock
from twisted.trial.unittest import SynchronousTestCase

from flocker.apiclient import FakeFlockerClient, Node

from benchmark.cluster import BenchmarkCluster
from benchmark._interfaces import IOperation, IProbe
from benchmark.operations.create_dataset import (
    CreateDatasetConvergence, CreateDatasetConvergenceProbe, EmptyClusterError,
)


class CreateDatasetTests(SynchronousTestCase):
    """
    CreateDataset operation tests.
    """

    def test_implements_IOperation(self):
        """
        CreateDatasetConvergence provides the IOperation interface.
        """
        verifyClass(IOperation, CreateDatasetConvergence)

    def test_implements_IProbe(self):
        """
        CreateDatasetConvergenceProbe provides the IProbe interface.
        """
        verifyClass(IProbe, CreateDatasetConvergenceProbe)

    def test_create_dataset(self):
        """
        CreateDataset probe waits for cluster to converge.
        """
        clock = Clock()

        node_id = uuid4()
        node = Node(uuid=node_id, public_address=IPAddress('10.0.0.1'))
        control_service = FakeFlockerClient([node], node_id)

        cluster = BenchmarkCluster(
            IPAddress('10.0.0.1'),
            lambda reactor: control_service,
            {},
            None,
        )
        operation = CreateDatasetConvergence(clock, cluster)
        d = operation.get_probe()

        def run_probe(probe):
            def cleanup(result):
                cleaned_up = probe.cleanup()
                cleaned_up.addCallback(lambda _ignored: result)
                return cleaned_up
            d = probe.run()
            d.addCallback(cleanup)
            return d
        d.addCallback(run_probe)

        clock.advance(1)
        self.assertNoResult(d)

        control_service.synchronize_state()

        # Advance the clock, because probe periodically polls the state.
        clock.advance(1)
        self.successResultOf(d)

    def test_empty_cluster(self):
        """
        CreateDataset fails if no nodes in cluster.
        """
        control_service = FakeFlockerClient()

        cluster = BenchmarkCluster(
            IPAddress('10.0.0.1'),
            lambda reactor: control_service,
            {},
            None,
        )

        d = CreateDatasetConvergence(Clock(), cluster).get_probe()

        self.failureResultOf(d, EmptyClusterError)
