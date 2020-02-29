#!/usr/bin/env python

from __future__ import print_function

import getpass
import sys
import re
import time
import _thread
from optparse import OptionParser

from minecraft import authentication
from minecraft.exceptions import YggdrasilError
from minecraft.networking.connection import Connection
from minecraft.networking.packets import Packet, clientbound, serverbound
from minecraft.compat import input


def get_options():
    parser = OptionParser()

    parser.add_option("-u", "--username", dest="username", default=None,
                      help="username to log in with")

    parser.add_option("-p", "--password", dest="password", default=None,
                      help="password to log in with")

    parser.add_option("-s", "--server", dest="server", default=None,
                      help="server host or host:port "
                           "(enclose IPv6 addresses in square brackets)")

    parser.add_option("-o", "--offline", dest="offline", action="store_true",
                      help="connect to a server in offline mode "
                           "(no password required)")

    parser.add_option("-d", "--dump-packets", dest="dump_packets",
                      action="store_true",
                      help="print sent and received packets to standard error")

    (options, args) = parser.parse_args()

    if not options.username:
        options.username = input("Enter your username: ")

    if not options.password and not options.offline:
        options.password = getpass.getpass("Enter your password (leave "
                                           "blank for offline mode): ")
        options.offline = options.offline or (options.password == "")

    if not options.server:
        options.server = input("Enter server host or host:port "
                               "(enclose IPv6 addresses in square brackets): ")
    # Try to split out port and address
    match = re.match(r"((?P<host>[^\[\]:]+)|\[(?P<addr>[^\[\]]+)\])"
                     r"(:(?P<port>\d+))?$", options.server)
    if match is None:
        raise ValueError("Invalid server address: '%s'." % options.server)
    options.address = match.group("host") or match.group("addr")
    options.port = int(match.group("port") or 25565)

    return options

class Player():
    def __init__(self, x, y, z, connection):
        self.x_pos = x
        self.y_pos = y
        self.z_pos = z
        self.connection = connection
        self.is_game_started = False

    def setCoords(self, x, y, z):
        self.x_pos = x
        self.y_pos = y
        self.z_pos = z

    def move(self, pos, dist):
        
        if pos == 'x':
            self.x_pos += float(dist)
            
        if pos == 'y':
            self.y_pos += float(dist)
            
        if pos == 'z':
            self.z_pos += float(dist)

        
    def send_packet_loop(self):
        while True:
            initial_time = time.time()

            packet = serverbound.play.PlayerPositionPacket()
            packet.x = self.x_pos
            packet.feet_y = self.y_pos
            packet.z = self.z_pos
            packet.on_ground = True
            self.connection.write_packet(packet)

            elapsed_time = time.time() - initial_time
            time.sleep(0.05 - elapsed_time)

    def get_pos(self, position_packet):
        self.setCoords(position_packet.x, position_packet.y, position_packet.z)
    
    def handle_join_game(self, join_game_packet):
        print('Connected.')
        self.is_game_started = True
    
def main_loop(connection):
    
    player = Player(0,0,0,connection)
    connection.register_packet_listener(player.get_pos, clientbound.play.PlayerPositionAndLookPacket)

    
    connection.register_packet_listener(player.handle_join_game, clientbound.play.JoinGamePacket)
    while player.is_game_started == False:
        time.sleep(0.05)
    _thread.start_new_thread(player.send_packet_loop, ())

    while True:
        try:
            text = input()
            if text == "/respawn":
                print("respawning...")
                packet = serverbound.play.ClientStatusPacket()
                packet.action_id = serverbound.play.ClientStatusPacket.RESPAWN
                connection.write_packet(packet)

            if text == "/move":
                pos = input("which way do you want to move?(x)(y)(z): ")
                dist = input("How many blocks do you want to move?: ")
                player.move(pos, dist)    
            
            else:
                packet = serverbound.play.ChatPacket()
                packet.message = text
                connection.write_packet(packet)
        except KeyboardInterrupt:
            print("Bye!")
            sys.exit()

def main():
    options = get_options()

    if options.offline:
        print("Connecting in offline mode...")
        connection = Connection(
            options.address, options.port, username=options.username)
    else:
        auth_token = authentication.AuthenticationToken()
        try:
            auth_token.authenticate(options.username, options.password)
        except YggdrasilError as e:
            print(e)
            sys.exit()
        print("Logged in as %s..." % auth_token.username)
        connection = Connection(
            options.address, options.port, auth_token=auth_token)

    if options.dump_packets:
        def print_incoming(packet):
            if type(packet) is Packet:
                # This is a direct instance of the base Packet type, meaning
                # that it is a packet of unknown type, so we do not print it.
                return
            print('--> %s' % packet, file=sys.stderr)

        def print_outgoing(packet):
            print('<-- %s' % packet, file=sys.stderr)

        connection.register_packet_listener(
            print_incoming, Packet, early=True)
        connection.register_packet_listener(
            print_outgoing, Packet, outgoing=True)



    def print_chat(chat_packet):
        print("Message (%s): %s" % (
            chat_packet.field_string('position'), chat_packet.json_data))
    
    connection.register_packet_listener(print_chat, clientbound.play.ChatMessagePacket)

    connection.connect()
    main_loop(connection)



if __name__ == "__main__":
    main()
