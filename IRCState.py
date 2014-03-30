import ProtobufSocket
import protocol_pb2 as proto

class Buffer:
    def __init__(self, buffer):
        self.id = buffer.id
        self.type = buffer.role.buffer_type
        self.name = buffer.role.name

class Network:

    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2

    def __init__(self, networkdef, methods):
        self.id = networkdef.id
        self.buffers = {}
        self.state = 0
        self.configuration = None
        self.methods = methods

        if networkdef.state == proto.NetworkListT.NetworkDisconnected:
            self.state = Network.STATE_DISCONNECTED
        elif networkdef.state == proto.NetworkListT.NetworkConnecting:
            self.state = Network.STATE_CONNECTING
        elif networkdef.state == proto.NetworkListT.NetworkConnected:
            self.state = Network.STATE_CONNECTED


    def add_buffer(self, buffer):

        self.buffers[buffer.id] = Buffer(buffer)

    def buffer_list(self):
        return sorted([v for k, v in self.buffers.items()])

    def get_state(self):
        return self.state
    def get_configuration(self):
        if self.configuration == None:
            m = 'get_configuration'
            if m in self.methods:
                method = self.methods[m]
                del self.methods[m]
                method()
            return None
        return self.configuration

class IRCState:

    def __init__(self, hostport, callbacks):

        self.networks = dict()

        self.logger = callbacks['logger']
        self.callbacks = callbacks

        self.socket = ProtobufSocket.ProtobufSocket(hostport, callbacks={

            'logger': lambda x: self.logger('PROTO: ' + x),
            'connect': self.on_connect,
            'close': self.on_close,
            'message': self.on_message
        })


    def on_connect(self):
        def attach_session_result(success):
            if success:
                    self.socket.get_network_list(self.on_network_list)
            else:
                self.logger('Unable to attach session!')

        self.socket.attach_session(0, attach_session_result)
        self.callbacks['core_connect']()

    def on_close(self):
        self.callbacks['core_close']()

    def network_list(self):
        return sorted([v for k, v in self.networks.items()])

    def on_network_list(self, network_list):

        for network in network_list:
            if network.id not in self.networks:
                self.networks[network.id] = Network(network, {
                    'get_configuration': lambda: self.socket.get_network_configuration(network.id, self.on_network_configuration)
                })

        self.callbacks['core_networklist'](self.network_list())

        # Refresh buffers
        for id in self.networks:
            self.socket.get_buffer_list(id, self.on_buffer_list)

    def on_network_configuration(self, network_id, network_configuration):

        if not network_id in self.networks:
            self.logger('Received network configuration for an unknown network')
            return

        network = self.networks[network_id]
        network.configuration = network_configuration

        # TODO: Use narrower callback
        self.callbacks['core_networklist'](self.network_list())

    def on_buffer_list(self, network_id, buffer_list):

        if not network_id in self.networks:
            self.logger('Received buffer list for an unknown network')
            return

        network = self.networks[network_id]

        for buffer in buffer_list:
            network.add_buffer(buffer)

        self.callbacks['core_bufferlist'](network)

    def on_message(self, packet):

        try:

            type = packet.packet_type

            if type == proto.RemoteMessage.NewBuffer:

                network_id = packet.network_id

                if not network_id in self.networks:
                    self.logger('Received NewBuffer for an unknown network')
                    return

                network = self.networks[network_id]
                network.add_buffer(packet.new_buffer)

                self.callbacks['core_newbuffer'](network)

            elif type == proto.RemoteMessage.Information:

                network_id = packet.network_id
                if not network_id in self.networks:
                    self.logger('Received information for an unknown network: ' + msg)
                    return

                msg = packet.information.msg
                self.logger('Information: ' + msg)

            elif type == proto.RemoteMessage.Connected:
                network_id = packet.network_id
                if not network_id in self.networks:
                    self.logger('Received \'connected\' for an unknown network!')
                    return

                network = self.networks[network_id]
                network.state = Network.STATE_CONNECTED
                self.callbacks['core_networklist'](self.network_list())

            elif type == proto.RemoteMessage.Disconnected:

                network_id = packet.network_id
                if not network_id in self.networks:
                    self.logger('Disconnected from an unknown network!')
                    return

                network = self.networks[network_id]
                network.state = Network.STATE_DISCONNECTED
                self.callbacks['core_networklist'](self.network_list())

            else:
                self.logger('Received unhandled message of type: ' + str(type))
                self.logger(str(packet))

        except Exception as e:
            self.logger('exception: ' + str(e))

    def core_connect(self, network_or_id, address):

        id = network_or_id
        if type(network_or_id) is Network:
            id = network_or_id.id

        self.socket.send_connect(id, address)
