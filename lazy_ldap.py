from twisted.application import service, internet
from twisted.internet.endpoints import serverFromString
from twisted.internet.protocol import ServerFactory
from twisted.python.components import registerAdapter
from twisted.python import log
from ldaptor.inmemory import fromLDIFFile
from ldaptor.interfaces import IConnectedLDAPEntry
from ldaptor.protocols.ldap import distinguishedname
from ldaptor.protocols.ldap.ldapserver import LDAPServer
from ldaptor.protocols import pureldap
from twisted.internet import reactor

import random
import tempfile
from cStringIO import StringIO
import sys

class LazyLDAPServer(LDAPServer):
    def queue(self, id, op):
        if not self.connected:
            raise LDAPServerConnectionLostException()
        msg = pureldap.LDAPMessage(op, id=id)
        if self.debug:
            log.msg('S->C %s' % repr(msg), debug=True)
        delay = random.randint(0, 10)
        reactor.callLater(delay, self.transport.write, str(msg))

class Tree(object):

    def __init__(self):
        LDIF = None
        with open('test.LDIF', 'r') as f:
            LDIF = f.read()

        self.f = StringIO(LDIF)
        d = fromLDIFFile(self.f)
        d.addCallback(self.ldifRead)

    def ldifRead(self, result):
        self.f.close()
        self.db = result

class LDAPServerFactory(ServerFactory):
    protocol = LazyLDAPServer

    def __init__(self, root):
        self.root = root

    def buildProtocol(self, addr):
        proto = self.protocol()
        proto.debug = self.debug
        proto.factory = self
        return proto

if __name__ == '__main__':
    random.seed()
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    else:
        port = 8080
    # First of all, to show logging info in stdout :
    log.startLogging(sys.stderr)
    # We initialize our tree
    tree = Tree()
    # When the LDAP Server protocol wants to manipulate the DIT, it invokes
    # `root = interfaces.IConnectedLDAPEntry(self.factory)` to get the root
    # of the DIT.  The factory that creates the protocol must therefore
    # be adapted to the IConnectedLDAPEntry interface.
    registerAdapter(
        lambda x: x.root,
        LDAPServerFactory,
        IConnectedLDAPEntry)
    factory = LDAPServerFactory(tree.db)
    factory.debug = True
    application = service.Application("ldaptor-server")
    myService = service.IServiceCollection(application)
    serverEndpointStr = "tcp:{0}".format(port)
    e = serverFromString(reactor, serverEndpointStr)
    d = e.listen(factory)
    reactor.run()