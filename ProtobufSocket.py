import asyncore, socket
import struct
import protocol_pb2 as proto
import traceback
import socket
import sys

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

        self.status = STATUS_CONNECTING

        # used to differentiate responses in the protocol
        self.tag_number = 0
        self.callbacks = dict()

        try:
            self.connect(hostport)
        except socket.error as e:
            self.logger(e)
        except socket.herror as e:
            self.logger(e)
        except socket.gaierror as e:
            self.logger(e)
        except Exception as e:
            self.logger(e)

    def handle_error(self):
        self.logger(traceback.format_exc())
        self.close()

    def handle_connect(self):
        try:
            self.status = STATUS_CONNECTED
            self.on_connect()
        except Exception as e:
            self.logger('handle_connect: ' + str(e))

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

                self.logger("<<< " + str(remote_message))

                if remote_message.HasField('tag') and remote_message.tag in self.callbacks:

                    callback = self.callbacks[remote_message.tag]
                    del self.callbacks[remote_message.tag]
                    callback(remote_message)
                else:
                    self.on_message(remote_message)

        except Exception as e:
            self.logger('exception: ' + str(e))

    def handle_write(self):
        if len(self.out_buffer) == 0 or self.status != STATUS_CONNECTED:
            return

        sent = self.send(self.out_buffer)
        self.out_buffer = self.out_buffer[sent:]

    #def handle_error(self):
    #    if self.status == STATUS_CONNECTING:
    #        self.logger('Unable to connect!')
    #    else:
    #        self.logger('Connection error!')
    #    self.close()

    def write_packet(self, packet, cb=None):

        if not packet.IsInitialized():
            self.logger('packet not initialized!')
            return

        if cb is not None:
            self.callbacks[self.tag_number] = cb

        packet.tag = self.tag_number
        self.tag_number = (self.tag_number + 1) % 100000

        raw_blob = packet.SerializeToString()
        body_length = len(raw_blob)
        full_packet = struct.pack('<I', body_length) + raw_blob

        self.logger('>>> ' + str(packet))
        self.out_buffer += full_packet

    def attach_session(self, id, cb):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.AttachSession
        packet.attach_session.session_id = id

        def handle_response(packet):
            if packet.packet_type == proto.RemoteMessage.Error:
                cb(False)
            elif packet.packet_type == proto.RemoteMessage.Success:
                cb(True)
            else:
                self.logger('Unknown reply to AttachSession: '+str(packet))
                cb(False)

        self.write_packet(packet, handle_response)

    def get_network_list(self, cb):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.GetNetworkList

        def handle_response(packet):
            if packet.packet_type == proto.RemoteMessage.NetworkList:
                cb(packet.network_list)
            else:
                self.logger('Unknown reply to GetNetworkList: '+str(packet))

        self.write_packet(packet, handle_response)

    def get_buffer_list(self, network_id, cb):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.GetBufferList
        packet.network_id = network_id

        def handle_response(packet):
            if packet.packet_type == proto.RemoteMessage.BufferList:
                cb(packet.network_id, packet.buffer_list)
            else:
                self.logger('Unknown reply to GetBufferList: '+str(packet))

        self.write_packet(packet, handle_response)

    def get_network_configuration(self, network_id, cb):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.GetNetworkConfiguration
        packet.network_id = network_id

        def handle_response(packet):
            if packet.packet.type == proto.RemoteMessage.NetworkConfiguration:
                cb(packet.network_configuration)
            else:
                self.logger('Unknown reply to GetNetworkConfiguration: '+str(packet))

        self.write_packet(packet, handle_response)

    def send_connect(self, network_id, address):
        packet = proto.RemoteCommand()
        packet.packet_type = proto.RemoteCommand.Connect
        packet.network_id = network_id
        packet.connect.address = address
        self.write_packet(packet, cb)
