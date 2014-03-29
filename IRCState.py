import ProtobufSocket
import protocol_pb2 as proto

class Buffer:
    def __init__(self, buffer):
        self.id = buffer.id
        self.type = buffer.role.buffer_type
        self.name = buffer.role.name

class Network:

    def __init__(self, networkdef):
        self.id = networkdef.id
        self.buffers = {}

    def add_buffer(self, buffer):

        self.buffers[buffer.id] = Buffer(buffer)

    def buffer_list(self):
        return sorted([v for k, v in self.buffers.items()])


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
        self.socket.send_attach_session(0)
        self.socket.send_get_network_list()

        self.callbacks['core_connect']()

    def on_close(self):
        self.callbacks['core_close']()

    def network_list(self):
        return sorted([v for k, v in self.networks.items()])

    def on_message(self, packet):

        try:

            type = packet.packet_type

            if type == proto.RemoteMessage.NetworkList:

                for network in packet.network_list:

                    if network.id not in self.networks:
                        self.networks[network.id] = Network(network)

                self.callbacks['core_networklist'](self.network_list())

                # Refresh buffers
                for id in self.networks:
                    self.socket.send_get_buffer_list(id)

            elif type == proto.RemoteMessage.BufferList:

                network_id = packet.network_id

                if not network_id in self.networks:
                    self.logger('Received buffer list for an unknown network')
                    return

                network = self.networks[network_id]

                for buffer in packet.buffer_list:
                    network.add_buffer(buffer)

                self.callbacks['core_bufferlist'](network)

            elif type == proto.RemoteMessage.NewBuffer:

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

            else:
                self.logger('Received unhandled message of type: ' + str(type))

        except Exception as e:
            self.logger('exception: ' + str(e))

    def core_connect(self, network, address):

        id = network
        if type(network) is Network:
            id = network.id

        self.socket.send_connect(id, address)
