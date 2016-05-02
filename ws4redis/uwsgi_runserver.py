# -*- coding: utf-8 -*-
import uwsgi
import gevent.select
from ws4redis.exceptions import WebSocketError
from ws4redis.wsgi_server import WebsocketWSGIServer

from iotsystem.authentication import _RedisUser
from iotsystem.redis_models import User
from iotsystem.models import Tag as TagDevice

def process_request(self,request):
    if request.META['HTTP_AUTHORIZATION'] is not None:
        access_token = str.split(request.META['HTTP_AUTHORIZATION'])[1]
        user = User.access_token.hgetall([access_token])
        user_class = _RedisUser(**user)
	if user:
            user_class.id = int(user['user_id'])
            user_class.is_staff = user['is_staff']
            user_class.is_superuser = user['is_superuser']

            #add groups
            tags = TagDevice.objects.filter(user_s_id=user_class.id)
            
            groups = []
            for tag in tags:
                groups.append(str(tag.dev_id))
            request.META["ws4redis:memberof"] =  groups;
            request.user = user_class
	    return True
        else: 
	    return False
    else:
        request.META["ws4redis:memberof"] =  ['debug'];
	return False

class uWSGIWebsocket(object):
    def __init__(self):
        self._closed = False

    def get_file_descriptor(self):
        """Return the file descriptor for the given websocket"""
        try:
            return uwsgi.connection_fd()
        except IOError as e:
            self.close()
            raise WebSocketError(e)

    @property
    def closed(self):
        return self._closed

    def receive(self):
        if self._closed:
            raise WebSocketError("Connection is already closed")
        try:
            return uwsgi.websocket_recv_nb()
        except IOError as e:
            self.close()
            raise WebSocketError(e)

    def flush(self):
        try:
            uwsgi.websocket_recv_nb()
        except IOError:
            self.close()

    def send(self, message, binary=None):
        try:
            uwsgi.websocket_send(message)
        except IOError as e:
            self.close()
            raise WebSocketError(e)

    def close(self, code=1000, message=''):
        self._closed = True


class uWSGIWebsocketServer(WebsocketWSGIServer):
    def upgrade_websocket(self, environ, start_response):
        uwsgi.websocket_handshake(environ['HTTP_SEC_WEBSOCKET_KEY'], environ.get('HTTP_ORIGIN', ''))
        return uWSGIWebsocket()

    def select(self, rlist, wlist, xlist, timeout=None):
        return gevent.select.select(rlist, wlist, xlist, timeout)

uWSGIWebsocketServer.process_request = process_request
