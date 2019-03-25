"""A set of libraries that are useful to both the proxy and regular servers."""

# This code uses Python 2.7. These imports make the 2.7 code feel a lot closer
# to Python 3. (They're also good changes to the language!)
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# THe Python socket API is based closely on the Berkeley sockets API which
# was originally written for the C programming language.
#
# https://en.wikipedia.org/wiki/Berkeley_sockets
#
# The API is more flexible than you need, and it does some quirky things to
# provide that flexibility. I recommend tutorials instead of complete
# descriptions because those can skip the archaic bits. (The API was released
# more than 35 years ago!)
import socket

import time
from threading import Timer

# Read this many bytes at a time of a command. Each socket holds a buffer of
# data that comes in. If the buffer fills up before you can read it then TCP
# will slow down transmission so you can keep up. We expect that most commands
# will be shorter than this.
COMMAND_BUFFER_SIZE = 256
MAX_CACHE_AGE_SEC = 60.0


def CreateServerSocket(port):
    """Creates a socket that listens on a specified port.

    Args:
      port: int from 0 to 2^16. Low numbered ports have defined purposes. Almost
          all predefined ports represent insecure protocols that have died out.
    Returns:
      An socket that implements TCP/IP.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', port))
    return sock


def ConnectClientToServer(server_sock):
    # Wait until a client connects and then get a socket that connects to the
    # client.
    server_sock.listen(1)
    client_socket, client_address = server_sock.accept()
    return client_socket, (client_address, client_socket.getsockname()[1])


def CreateClientSocket(server_addr, port):
    """Creates a socket that connects to a port on a server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_addr, port))
    return sock


def ReadCommand(sock):
    """Read a single command from a socket. The command must end in newline."""
    return sock.recv(COMMAND_BUFFER_SIZE)


def ParseCommand(command):
    """Parses a command and returns the command name, first arg, and remainder.

    All commands are of the form:
        COMMAND arg1 remaining text is called remainder
    Spaces separate the sections, but the remainder can contain additional spaces.
    The returned values are strings if the values are present or `None`. Trailing
    whitespace is removed.

    Args:
      command: string command.
    Returns:
      command, arg1, remainder. Each of these can be None.
    """
    args = command.strip().split(' ')
    command = None
    if args:
        command = args[0]
    arg1 = None
    if len(args) > 1:
        arg1 = args[1]
    remainder = None
    if len(args) > 2:
        remainder = ' '.join(args[2:])
    return command, arg1, remainder


"""
Blueprint of recrods store in the database. 
Stores the time by default, only used when max_age specified in the get request. 
"""


class Record:
    def __init__(self, value, stored_time=None):
        self.value = value
        self.stored_time = time.time() if not stored_time else stored_time

    def get_time_elapsed(self, time):
        return time - self.stored_time


class InvalidRecordFormatException(Exception):
    pass


class InvalidRecordTypeException(Exception):
    pass


class KeyValueStore(object):
    """A dictionary of strings keyed by strings.

    The values can time out once they get sufficiently old. Otherwise, this
    acts much like a dictionary.
    """

    """
    If fileName is passed, the dictionary is initialized with the records 
    in the file. 

    If isTimer is set to true, a callback is registered to clean the store 
    every 5 seconds if the time-elapsed is greated than MAX_CACHE_AGE_SEC
    """

    def __init__(self, fileName=None, isTimer=False):
        self.store = {}
        if fileName:
            self.read_file_into_store(fileName)

        def callback_to_clean_store(*args):
            st = args[0]
            for key in list(st):
                if st[key].get_time_elapsed(time.time()) > MAX_CACHE_AGE_SEC:
                    print("Removing key %s due to timeout" % key)
                    del st[key]
            t = Timer(5,
                      callback_to_clean_store, [st])
            t.start()

        if isTimer:
            print("Setting timer callback")
            # Start a timer that cleans the store every 5 seconds.
            t = Timer(5, callback_to_clean_store, [self.store])
            t.start()

    def read_file_into_store(self, fileName):
        """
        Helper method to read records from a text file. 
        """
        with open(fileName, 'r') as fileHandle:
            try:
                for record in fileHandle.readlines():
                    record = record.split(',')
                    if len(record) != 3:
                        raise InvalidRecordFormatException(
                            "File: %s does not have the records in proper format" % fileName)
                    self.store[record[0]] = Record(record[1], float(record[2]))
            except ValueError:
                raise InvalidRecordTypeException(
                    "File %s have records with improper data type" % fileName)

    def GetValue(self, key, max_age_in_sec=None):
        """Gets a cached value or `None`.

        Values older than `max_age_in_sec` seconds are not returned.

        Args:
          key: string. The name of the key to get.
          max_age_in_sec: float. Maximum time since the value was placed in the
            KeyValueStore. If not specified then values do not time out.
        Returns:
          None or the value.
        """
        record = self.store.get(key, None)
        if not record:
            return None
        if not max_age_in_sec:
            return record.value
        return record.value if record.get_time_elapsed(time.time()) < max_age_in_sec else None

    def StoreValue(self, key, value):
        """Stores a value under a specific key.
        Overwrites if an existing record with the same key exists. 

        Args:
          key: string. The name of the value to store.
          value: string. A value to store.
        """
        self.store[key] = Record(value)

    def Keys(self):
        """Returns a list of all keys in the datastore."""
        return self.store.keys()

    def __str__(self):
        """
        Helper method to write the records to a text file. 
        """
        return_string = ""
        for key, record in self.store.iteritems():
            return_string += "% s, % s, % d\n" % (key,
                                                  record.value, record.stored_time)
        return return_string
