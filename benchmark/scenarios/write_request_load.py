# Copyright 2015 ClusterHQ Inc.  See LICENSE file for details.
"""
Read request load scenario for the control service benchmarks.
"""
import random

from zope.interface import implementer

from twisted.internet.defer import CancelledError

from flocker.common import timeout

from .._interfaces import IRequestScenarioSetup

from ._rate_measurer import DEFAULT_SAMPLE_SIZE

from ._request_load import (
    RequestLoadScenario, NoNodesFound
)


class DatasetCreationTimeout(Exception):
    """
    The dataset could not be created within the specified time.
    """


@implementer(IRequestScenarioSetup)
class WriteRequest(object):
    """
    Implementation of the write setup.
    :ivar reactor: Reactor to use.
    :ivar cluster: `BenchmarkCluster` containing the control service.
    :ivar timeout: Maximum time in seconds to wait until the dataset is
        created.
    """
    def __init__(self, reactor, cluster, timeout=10):
        self.control_service = cluster.get_control_service(reactor)
        self.reactor = reactor
        self.timeout = timeout
        self.nodes = None
        self.dataset_node = None
        self.dataset_id = ""

    def _create_dataset(self, node):
        """
        Creates a dataset in the node given.

        :param node: node where we want the dataset.

        :return: A Deferred that fires when the dataset has been created.

        :raises: `DatasetCreationTimeout` if the creation goes wrong.
        """
        self.dataset_node = node
        creating = self.control_service.create_dataset(
            primary=node.uuid)

        def handle_timeout_and_errors(failure):
            failure.trap(CancelledError)
            raise DatasetCreationTimeout()

        timeout(self.reactor, creating, self.timeout)

        creating.addErrback(handle_timeout_and_errors)
        return creating

    def _get_dataset_node(self, nodes):
        """
        Selects the node where the dataset will be created.

        :param nodes: list of `Node` where we will chose one
            to create the dataset.

        :return: the selected `Node`.
        :raise: `NoNodesFound` if the given list of nodes was empty.
        """
        if not nodes:
            raise NoNodesFound()
        return random.choice(nodes)

    def _set_dataset_id(self, dataset):
        """
        Function to set the value of the dataset id once the dataset
        has been created.
        :param nodes: listed nodes.
        """
        self.dataset_id = dataset.dataset_id

    def run_setup(self):
        """
        Executes the setup and starts running the write scenario.

        :return: A Deferred that fires when the desired scenario is
            established (e.g. that a certain load is being applied).
        """
        # List all the nodes registered in the control service
        d = self.control_service.list_nodes()
        d.addCallback(self._get_dataset_node)
        # Once we have the list of nodes, we will create a dataset.
        # We cannot start the scenario until we have a working dataset, so
        # `_create_dataset` will work like a setup of the write scenario
        d.addCallback(self._create_dataset)
        d.addCallback(self._set_dataset_id)
        return d

    def make_request(self):
        if self.dataset_node is None:
            # Rise exception
            raise DatasetCreationTimeout
        return self.control_service.move_dataset(
            self.dataset_node.uuid,
            self.dataset_id
            )


def write_request_load_scenario(reactor, cluster, request_rate=10,
                                sample_size=DEFAULT_SAMPLE_SIZE, timeout=45):
    """
    Factory that will initialise and return a scenario that places load on
    the cluster by performing write requests at a specified rate.

    :param reactor: Reactor to use.
    :param cluster: `BenchmarkCluster` containing the control service.
    :param request_rate: The target number of requests per second.
    :param sample_size: The number of samples to collect when measuring
        the rate.
    :param timeout: Maximum time in seconds to wait for the requested
        rate to be reached.
    """
    return RequestLoadScenario(
        reactor,
        WriteRequest(reactor, cluster),
        request_rate=request_rate,
        sample_size=sample_size,
        timeout=timeout,
    )

