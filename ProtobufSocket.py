import asyncore, socket
import struct
import protocol_pb2 as proto

STATUS_CONNECTING = 0
STATUS_CONNECTED = 1
STATUS_DISCONNECTED = 2

class ProtobufSocket(asyncore.dispatcher):

    def __init__(self, hostport, callbacks):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.callbacks = callbacks
        self.in_buffer = bytearray()
        self.out_buffer = bytearray()

        self.logger = self.callbacks['logger']
        self.on_connect = self.callbacks['connect']
        self.on_close = self.callbacks['close']
        self.on_message = self.callbacks['message']

        self.logger('Connecting to %s:%s' % hostport)

        self.connect(hostport)
        self.status = STATUS_CONNECTING

    def handle_connect(self):
        self.status = STATUS_CONNECTED
        self.on_connect()

    def handle_close(self):
        self.status = STATUS_DISCONNECTED
        self.on_close()
        self.close()

    def writable(self):
        return len(self.out_buffer) > 0 or self.status == STATUS_CONNECTING

    def handle_read(self):

        self.in_buffer += self.recv(8192)

        # each packet begins with a 4-byte little-endian u32 denoting its length
        header_length = 4

        try:
            while True:

                if len(self.in_buffer) < header_length:
                    break

                body_length = struct.unpack('<I', self.in_buffer[0:header_length])[0]

                if len(self.in_buffer) < header_length+body_length:
                    break

                # Consume packet
                raw_blob = self.in_buffer[header_length: header_length + body_length]
                self.in_buffer = self.in_buffer[header_length + body_length:]

                remote_message = proto.RemoteMessage()
                remote_message.ParseFromString(bytes(raw_blob))

                if not remote_message.IsInitialized():
                    self.logger('Server bug? Received invalid message: len=' + str(body_length) + ' ' + str(raw_blob))
                    break

                self.on_message(remote_message)

        except Exception as e:
            self.logger('exception: ' + str(e))

    def handle_write(self):
        if len(self.out_buffer) == 0 or self.status != STATUS_CONNECTED:
            return

        sent = self.send(self.out_buffer)
        self.out_buffer = self.out_buffer[sent:]

    def handle_error(self):
        self.logger('error')
        self.close()

    def write_packet(self, packet):

        if not packet.IsInitialized():
            self.logger('packet not initialized!')
            return

        raw_blob = packet.SerializeToString()
        body_length = len(raw_blob)
        full_packet = struct.pack('<I', body_length) + raw_blob

        self.logger('sending: ' + str(packet))
        #self.logger('sending: ' + str(full_packet))
        self.out_buffer += full_packet

    def send_attach_session(self, id):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.AttachSession
        packet.attach_session.session_id = id
        self.write_packet(packet)

    def send_get_network_list(self):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.GetNetworkList
        self.write_packet(packet)

    def send_get_buffer_list(self, network_id):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.GetBufferList
        packet.network_id = network_id
        self.write_packet(packet)

    def send_connect(self, network_id, address):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.Connect
        packet.network_id = network_id
        packet.connect.address = address
        self.write_packet(packet)
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.Register
        packet.network_id = network_id
        packet.register.nickname = 'foobar'
        self.write_packet(packet)