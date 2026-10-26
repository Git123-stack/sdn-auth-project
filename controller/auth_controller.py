import ipaddress
import json

from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import packet, ethernet, ipv4, ether_types
from ryu.ofproto import ofproto_v1_3
from webob import Response

SERVER_IP = "10.0.0.1"
AUTHENTICATED = set()   # IPs that passed authentication
APP_NAME = "auth_app"


class AuthController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"wsgi": WSGIApplication}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        kwargs["wsgi"].register(AuthRest, {APP_NAME: self})

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp
        ofp, parser = dp.ofproto, dp.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)

    def add_flow(self, dp, priority, match, actions, idle_timeout=0):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, match=match,
                                instructions=inst, idle_timeout=idle_timeout)
        dp.send_msg(mod)

    def authenticate(self, ip):
        AUTHENTICATED.add(ip)
        self.logger.info("AUTHENTICATED %s", ip)
        # remove any drop rules already installed for this source
        for dp in self.datapaths.values():
            ofp, parser = dp.ofproto, dp.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=ip)
            mod = parser.OFPFlowMod(datapath=dp, command=ofp.OFPFC_DELETE,
                                    out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
                                    match=match)
            dp.send_msg(mod)

    def is_allowed(self, src_ip, dst_ip):
        # Anyone may talk to/from the auth server; other traffic
        # needs the sender to be authenticated.
        if src_ip == SERVER_IP or dst_ip == SERVER_IP:
            return True
        return src_ip in AUTHENTICATED

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        self.mac_to_port.setdefault(dp.id, {})
        self.mac_to_port[dp.id][eth.src] = in_port

        ip = pkt.get_protocol(ipv4.ipv4)
        if ip and not self.is_allowed(ip.src, ip.dst):
            self.logger.info("BLOCKED %s -> %s", ip.src, ip.dst)
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=ip.src, ipv4_dst=ip.dst)
            self.add_flow(dp, 10, match, [], idle_timeout=30)   # empty actions = drop
            return

        out_port = self.mac_to_port[dp.id].get(eth.dst, ofp.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofp.OFPP_FLOOD and ip:
            match = parser.OFPMatch(in_port=in_port, eth_type=0x0800, ipv4_src=ip.src, ipv4_dst=ip.dst)
            self.add_flow(dp, 1, match, actions, idle_timeout=60)
        out = parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=msg.data)
        dp.send_msg(out)


class AuthRest(ControllerBase):
    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.app = data[APP_NAME]

    @route("auth", "/auth/login", methods=["POST"])
    def login(self, req, **kwargs):
        try:
            ip = str(json.loads(req.body.decode("utf-8"))["ip"])
            ipaddress.ip_address(ip)
        except (ValueError, KeyError, TypeError):
            body = json.dumps({"error": "send JSON like {\"ip\": \"10.0.0.2\"}"}).encode()
            return Response(status=400, content_type="application/json", body=body)
        self.app.authenticate(ip)
        return self._reply()

    @route("auth", "/auth/status", methods=["GET"])
    def status(self, req, **kwargs):
        return self._reply()

    def _reply(self):
        body = json.dumps({"authenticated": sorted(AUTHENTICATED)}).encode()
        return Response(content_type="application/json", body=body)