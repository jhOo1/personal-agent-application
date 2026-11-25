"""Application-local DNS cache; standard HTTPS still checks the original hostname."""
from __future__ import annotations
import http.client
import ipaddress
import json
import os
import socket
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from .common import sha


class DNSCache:
    def __init__(self,path:Path|None=None,ttl=300.,max_stale=1800.,retry_spacing=30.,lookup=None,clock=None,event=None):
        if not 0<ttl<=max_stale or retry_spacing<=0:raise ValueError('invalid DNS cache limits')
        self.path=Path(path) if path else None
        self.ttl,self.max_stale,self.retry_spacing=ttl,max_stale,retry_spacing
        self.lookup,self.clock,self.event=lookup or socket.getaddrinfo,clock or time.time,event or (lambda **k:None)
        self.lock=threading.RLock();self.entries={};self.next_lookup={}
        if self.path and self.path.exists():
            data=json.loads(self.path.read_text())
            if data.get('version')!=1:raise ValueError('unsupported private DNS cache')
            for key,item in data['entries'].items():
                addresses=[]
                for family,kind,proto,canon,address in item['addresses']:
                    parsed=ipaddress.ip_address(address[0])
                    if family not in (socket.AF_INET,socket.AF_INET6) or kind!=socket.SOCK_STREAM:raise ValueError('invalid cached address')
                    if parsed.version!=(4 if family==socket.AF_INET else 6):raise ValueError('cached address family mismatch')
                    addresses.append((family,kind,proto,canon,tuple(address)))
                self.entries[key]={'saved_at':item['saved_at'],'addresses':addresses}

    def _persist(self):
        if not self.path:return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd, name=tempfile.mkstemp(prefix=self.path.stem+'.',suffix='.tmp',dir=self.path.parent)
        temporary=Path(name)
        try:
            with os.fdopen(fd,'w') as out:
                json.dump({'version':1,'entries':self.entries},out)
                out.flush();os.fsync(out.fileno())
            temporary.replace(self.path)
            os.chmod(self.path,0o600)
        finally:
            temporary.unlink(missing_ok=True)

    def resolve(self,host,port):
        key=sha([host.casefold(),port]);label=key[:16]
        with self.lock:
            now=self.clock();entry=self.entries.get(key)
            age=now-entry['saved_at'] if entry else None
            if age is not None and age<0:entry=None;age=None
            if entry and age<=self.ttl:return entry['addresses']
            if entry and age<=self.max_stale and now<self.next_lookup.get(key,0):return entry['addresses']
            try:
                addresses=self.lookup(host,port,0,socket.SOCK_STREAM)
                if not addresses:raise socket.gaierror(socket.EAI_NONAME,'empty DNS result')
            except socket.gaierror as exc:
                self.next_lookup[key]=now+self.retry_spacing
                if entry and age<=self.max_stale:
                    self.event(status='dns_stale_cache_fallback_before_connection',host_hash=label,cache_age_seconds=round(age,3),errno=exc.errno,tls_hostname_verification_unchanged=True)
                    return entry['addresses']
                self.event(status='dns_resolution_failed_without_usable_cache',host_hash=label,errno=exc.errno)
                raise
            self.entries[key]={'saved_at':self.clock(),'addresses':addresses}
            self.next_lookup.pop(key,None);self._persist()
            self.event(status='dns_cache_refreshed_before_connection',host_hash=label,address_count=len(addresses),tls_hostname_verification_unchanged=True)
            return addresses

    def create_connection(self,address,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,source_address=None,*,all_errors=False):
        host,port=address;errors=[]
        for family,kind,proto,canon,sockaddr in self.resolve(host,port):
            sock=None
            try:
                sock=socket.socket(family,kind,proto)
                if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:sock.settimeout(timeout)
                if source_address:sock.bind(source_address)
                sock.connect(sockaddr)
                return sock
            except OSError as exc:
                errors.append(exc)
                if sock is not None:sock.close()
        if all_errors:raise ExceptionGroup('all cached addresses failed',errors)
        if errors:raise errors[-1]
        raise OSError('DNS supplied no usable addresses')


class CachedDNSHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self,*args,resolver,**kwargs):
        super().__init__(*args,**kwargs)
        # Standard HTTPSConnection.connect wraps this socket using self.host as SNI
        # and verifies its certificate. Only TCP address resolution is replaced.
        self._create_connection=resolver.create_connection


class CachedDNSHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self,resolver,context=None):
        super().__init__(context=context);self.resolver=resolver
    def https_open(self,req):
        def connection(*args,**kwargs):
            return CachedDNSHTTPSConnection(*args,resolver=self.resolver,**kwargs)
        return self.do_open(connection,req,context=self._context)
