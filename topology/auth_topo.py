#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.cli import CLI
from mininet.log import setLogLevel

NUM_CLIENTS = 3                 # change this to add/remove clients
SERVER_IP = "10.0.0.1"          # h1 = auth server
CONTROLLER_IP = "127.0.0.1"
CONTROLLER_PORT = 6653


class AuthTopo(Topo):
    def build(self, num_clients=NUM_CLIENTS):
        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        server = self.addHost("h1", ip=SERVER_IP + "/24", mac="00:00:00:00:00:01")
        self.addLink(server, s1)
        for i in range(num_clients):
            n = i + 2
            h = self.addHost("h%d" % n, ip="10.0.0.%d/24" % n,
                             mac="00:00:00:00:00:%02x" % n)
            self.addLink(h, s1)


def run():
    net = Mininet(topo=AuthTopo(), switch=OVSSwitch, controller=None)
    net.addController("c0", controller=RemoteController,
                      ip=CONTROLLER_IP, port=CONTROLLER_PORT)
    net.start()
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
