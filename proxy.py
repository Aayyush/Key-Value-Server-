"""A proxy server that forwards requests from one port to another server.

To run this using Python 2.7:

% python proxy.py

It listens on a port (`LISTENING_PORT`, below) and forwards commands to the
server. The server is at `SERVER_ADDRESS`:`SERVER_PORT` below.
"""

# This code uses Python 2.7. These imports make the 2.7 code feel a lot closer
# to Python 3. (They're also good changes to the language!)
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import library
import optparse

# Where to find the server. This assumes it's running on the smae machine
# as the proxy, but on a different port.
SERVER_ADDRESS = 'localhost'
SERVER_PORT = 7777

# The port that the proxy server is going to occupy. This could be the same
# as SERVER_PORT, but then you couldn't run the proxy and the server on the
# same machine.
LISTENING_PORT = 8888

# Cache values retrieved from the server for this long.
MAX_CACHE_AGE_SEC = 60.0  # 1 minute


def ForwardCommandToServer(command, server_addr, server_port):
    """Opens a TCP socket to the server, sends a command, and returns response.

    Args:
      command: A single line string command with no newlines in it.
      server_addr: A string with the name of the server to forward requests to.
      server_port: An int from 0 to 2^16 with the port the server is listening on.
    Returns:
      A single line string response with no newlines.
    """
    socket = library.CreateClientSocket(server_addr, server_port)
    socket.send(command)

    # Wait to receive the data from the server socket.
    return library.ReadCommand(socket)


def ProxyClientCommand(sock, server_addr, server_port, cache):
    """Receives a command from a client and forwards it to a server:port.

    A single command is read from `sock`. That command is passed to the specified
    `server`:`port`. The response from the server is then passed back through
    `sock`.

    Args:
      sock: A TCP socket that connects to the client.
      server_addr: A string with the name of the server to forward requests to.
      server_port: An int from 0 to 2^16 with the port the server is listening on.
      cache: A KeyValueStore object that maintains a temorary cache.
      max_age_in_sec: float. Cached values older than this are re-retrieved from
        the server.
    """
    command_line = library.ReadCommand(sock)

    cmd, name, text = library.ParseCommand(command_line)

    if cmd == "GET":
        if cache.GetValue(name, MAX_CACHE_AGE_SEC):
            print('Key %s in the cache.' % name)
            sock.send("Key: {0}, Value: {1}\n".format(
                name, cache.GetValue(name, MAX_CACHE_AGE_SEC)))
            return

        # Get record from the server, and update the cache.
        serverResponse = ForwardCommandToServer(
            command_line, server_addr, server_port)
        cache.StoreValue(name, serverResponse)
    elif cmd == "PUT":
        print('Writing %s: %s to the cache' % (name, text))
        cache.StoreValue(name, text)
        serverResponse = ForwardCommandToServer(
            command_line, server_addr, server_port)
    elif cmd == "DUMP":
        serverResponse = ForwardCommandToServer(
            command_line, server_addr, server_port)
    else:
        return

    # Forward the server response to the client.
    print("Forwarding the response from the server to the client")
    sock.send(serverResponse)


def main(records_file=None):
    # Listen on a specified port...
    server_sock = library.CreateServerSocket(LISTENING_PORT)
    if records_file:
        try:
            database = library.KeyValueStore(
                fileName=records_file, isTimer=True)
        except library.InvalidRecordFormatException as e:
            print(e)
            print("Initializing an empty cache.")
            database = library.KeyValueStore()
        except library.InvalidRecordTypeException as e:
            print(e)
            print("Initializing an empty cache.")
            database = library.KeyValueStore()
    else:
        cache = library.KeyValueStore(isTimer=True)
    # Accept incoming commands indefinitely.
    try:
        while True:
            # Wait until a client connects and then get a socket that connects to the
            # client.
            client_sock, (address, port) = library.ConnectClientToServer(
                server_sock)
            print('Received connection from %s:%d' % (address, port))
            ProxyClientCommand(client_sock, SERVER_ADDRESS, SERVER_PORT,
                               cache)
            client_sock.close()
    except KeyboardInterrupt:
        # Close server socket.
        # Write the records to a file for later use.
        server_sock.close()
        with open("proxy-records.txt", 'w') as fileHandle:
            fileHandle.write(str(cache))


parser = optparse.OptionParser()
parser.add_option('-d', '--database', action='store',
                  dest='database', default=None)
option, args = parser.parse_args()

main(option.database)
