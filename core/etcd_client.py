"""
ETCDClient - Handles all etcd v3 API operations for Traefik configuration.

This module provides a clean interface for interacting with etcd to manage
Traefik HTTP/TCP/UDP routers, services, and middlewares.
"""

import requests
import base64
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict

from .models import (
    Router, TCPRouter, UDPRouter, Service, MiddlewareType,
    middleware_to_dict, middleware_from_dict,
    Server, LoadBalancerService, HealthCheck, StickyCookie,
    WeightedService, MirrorService, FailoverService, ServiceType,
    TCPServer, TCPService, UDPServer, UDPService,
    TLSConfig, Observability,
    TLSOptions, TLSStore, ServersTransport, TCPServersTransport,
    TCPMiddlewareType,
)


class ETCDException(Exception):
    """Base exception for etcd operations."""
    pass


class ETCDClient:
    """
    Client for interacting with etcd v3 API.
    
    All Traefik configuration is stored in etcd with keys following patterns:
    - traefik/http/routers/<name>/*
    - traefik/http/services/<name>/*
    - traefik/http/middlewares/<name>/*
    - traefik/tcp/routers/<name>/*
    - traefik/tcp/services/<name>/*
    - traefik/udp/routers/<name>/*
    - traefik/udp/services/<name>/*
    """
    
    def __init__(self, etcd_url: str = "http://localhost:2379"):
        """
        Initialize etcd client.
        
        Args:
            etcd_url: etcd server URL
        """
        self.etcd_url = etcd_url.rstrip('/')
        self.api_url = f"{self.etcd_url}/v3"
        self.timeout = 5
        
    def _encode_key(self, key: str) -> str:
        """Encode key to base64 for etcd v3 API."""
        return base64.b64encode(key.encode()).decode()
    
    def _decode_key(self, encoded: str) -> str:
        """Decode base64 key from etcd v3 API."""
        return base64.b64decode(encoded).decode()
    
    def _encode_value(self, value: str) -> str:
        """Encode value to base64 for etcd v3 API."""
        return base64.b64encode(value.encode()).decode()
    
    def _decode_value(self, encoded: str) -> str:
        """Decode base64 value from etcd v3 API."""
        return base64.b64decode(encoded).decode()

    def _extract_tls_cert_resolver(self, tls: Any) -> str:
        """Extract cert resolver from TLS object/dict with backward compatibility."""
        if not tls:
            return ''

        if isinstance(tls, dict):
            return (
                tls.get('cert_resolver')
                or tls.get('certresolver')
                or ''
            )

        return getattr(tls, 'cert_resolver', '') or getattr(tls, 'certresolver', '') or ''

    def _extract_tls_options(self, tls: Any) -> str:
        """Extract TLS options from TLS object/dict."""
        if not tls:
            return ''
        if isinstance(tls, dict):
            return tls.get('options', '')
        return getattr(tls, 'options', '')

    def _extract_tls_domains(self, tls: Any) -> List[Any]:
        """Extract TLS domains from TLS object/dict."""
        if not tls:
            return []
        if isinstance(tls, dict):
            domains = tls.get('domains', [])
            return domains if isinstance(domains, list) else []
        domains = getattr(tls, 'domains', [])
        return domains if isinstance(domains, list) else []
    
    def _request(self, endpoint: str, data: Dict) -> Dict:
        """
        Make request to etcd API.
        
        Args:
            endpoint: API endpoint (e.g., 'kv/put', 'kv/range')
            data: Request payload
            
        Returns:
            Response JSON
            
        Raises:
            ETCDException: On request failure
        """
        try:
            response = requests.post(
                f"{self.api_url}/{endpoint}",
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ETCDException(f"etcd request failed: {e}")
    
    def put(self, key: str, value: str) -> bool:
        """
        Put a key-value pair in etcd.
        
        Args:
            key: Key path
            value: Value to store
            
        Returns:
            True on success
        """
        try:
            self._request('kv/put', {
                'key': self._encode_key(key),
                'value': self._encode_value(value)
            })
            return True
        except ETCDException:
            return False
    
    def get(self, key: str) -> Optional[str]:
        """
        Get a value from etcd.
        
        Args:
            key: Key path
            
        Returns:
            Value if found, None otherwise
        """
        try:
            response = self._request('kv/range', {
                'key': self._encode_key(key)
            })
            
            if 'kvs' in response and response['kvs']:
                first_kv = response['kvs'][0]
                if 'value' not in first_kv:
                    return None
                return self._decode_value(first_kv['value'])
            return None
        except ETCDException:
            return None
    
    def get_prefix(self, prefix: str) -> Dict[str, str]:
        """
        Get all key-value pairs with given prefix.
        
        Args:
            prefix: Key prefix
            
        Returns:
            Dict of key-value pairs
        """
        try:
            # Get range from prefix to prefix+1 (lexicographic range)
            # For prefix "traefik/", this becomes "traefik0"
            # For prefix "/traefik/", this becomes "/traefik0"
            range_end = prefix[:-1] + chr(ord(prefix[-1]) + 1)
            
            response = self._request('kv/range', {
                'key': self._encode_key(prefix),
                'range_end': self._encode_key(range_end),
                'limit': 0  # 0 = unlimited, ensures all keys are returned
            })
            
            result = {}
            if 'kvs' in response:
                for kv in response['kvs']:
                    if 'key' not in kv:
                        continue
                    key = self._decode_key(kv['key'])
                    if 'value' not in kv:
                        # Defensive handling for malformed/partial etcd responses
                        continue
                    value = self._decode_value(kv['value'])
                    result[key] = value
            
            return result
        except ETCDException:
            return {}
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from etcd.
        
        Args:
            key: Key path
            
        Returns:
            True on success
        """
        try:
            self._request('kv/deleterange', {
                'key': self._encode_key(key)
            })
            return True
        except ETCDException:
            return False
    
    def delete_prefix(self, prefix: str) -> bool:
        """
        Delete all keys with given prefix.
        
        Args:
            prefix: Key prefix
            
        Returns:
            True on success
        """
        try:
            # Get range from prefix to prefix+1 (lexicographic range)
            range_end = prefix[:-1] + chr(ord(prefix[-1]) + 1)
            
            self._request('kv/deleterange', {
                'key': self._encode_key(prefix),
                'range_end': self._encode_key(range_end)
            })
            return True
        except ETCDException:
            return False
    
    # HTTP Router Operations
    
    def get_http_router(self, name: str) -> Optional[Router]:
        """
        Get HTTP router by name.
        
        Args:
            name: Router name
            
        Returns:
            Router object if found, None otherwise
        """
        prefix = f"traefik/http/routers/{name}/"
        kvs = self.get_prefix(prefix)
        
        if not kvs:
            return None
        
        # Parse router from etcd keys
        router_data = {
            'name': name,
            'rule': '',
            'service': '',
            'entrypoints': [],
            'middlewares': [],
            'priority': 0,
            'tls': None,
            'observability': None,
        }
        
        tls_data = {}
        obs_data = {}
        
        for key, value in kvs.items():
            field = key.replace(prefix, '')
            
            if field == 'rule':
                router_data['rule'] = value
            elif field == 'service':
                router_data['service'] = value
            elif field == 'entrypoints':
                router_data['entrypoints'] = [value]
            elif field.startswith('entrypoints/'):
                router_data['entrypoints'].append(value)
            elif field == 'middlewares':
                router_data['middlewares'] = [value]
            elif field.startswith('middlewares/'):
                router_data['middlewares'].append(value)
            elif field == 'priority':
                router_data['priority'] = int(value)
            elif field.startswith('observability/'):
                obs_key = field.replace('observability/', '')
                obs_data[obs_key] = value
            elif field.startswith('tls'):
                subfield = field.replace('tls/', '')
                normalized_subfield = subfield.lower().replace('_', '')
                if subfield == 'tls':
                    tls_data['enabled'] = value.lower() == 'true'
                elif normalized_subfield == 'certresolver':
                    tls_data['cert_resolver'] = value
                    tls_data['enabled'] = True
                elif subfield == 'options':
                    tls_data['options'] = value
                    tls_data['enabled'] = True
                elif subfield.startswith('domains/'):
                    tls_data['enabled'] = True
        
        # Construct TLSConfig if TLS is enabled
        if tls_data.get('enabled'):
            router_data['tls'] = TLSConfig(
                cert_resolver=tls_data.get('cert_resolver', ''),
                options=tls_data.get('options', ''),
                domains=[]
            )
        
        # Construct Observability if any observability keys
        if obs_data:
            router_data['observability'] = Observability(
                access_logs=obs_data.get('accesslogs', 'true').lower() == 'true',
                metrics=obs_data.get('metrics', 'true').lower() == 'true',
                tracing=obs_data.get('tracing', 'true').lower() == 'true',
            )
        
        return Router(**router_data)
    
    def list_http_routers(self) -> List[Router]:
        """
        List all HTTP routers.
        
        Returns:
            List of Router objects
        """
        kvs = self.get_prefix("traefik/http/routers/")
        
        # Group by router name
        routers_data = {}
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                name = parts[3]
                if name not in routers_data:
                    routers_data[name] = name
        
        # Get full router for each name
        routers = []
        for name in routers_data.values():
            router = self.get_http_router(name)
            if router:
                routers.append(router)
        
        return routers
    
    def put_http_router(self, router: Router) -> bool:
        """
        Save HTTP router to etcd.
        
        Args:
            router: Router object
            
        Returns:
            True on success
        """
        prefix = f"traefik/http/routers/{router.name}/"
        
        # Delete existing keys
        self.delete_prefix(prefix)
        
        # Put router fields
        success = True
        success &= self.put(f"{prefix}rule", router.rule)
        success &= self.put(f"{prefix}service", router.service)
        
        for i, ep in enumerate(router.entrypoints):
            success &= self.put(f"{prefix}entrypoints/{i}", ep)
        
        for i, mw in enumerate(router.middlewares):
            success &= self.put(f"{prefix}middlewares/{i}", mw)
        
        if router.priority > 0:
            success &= self.put(f"{prefix}priority", str(router.priority))
        
        # Observability
        if router.observability:
            obs = router.observability
            success &= self.put(f"{prefix}observability/accesslogs", str(obs.access_logs).lower())
            success &= self.put(f"{prefix}observability/metrics", str(obs.metrics).lower())
            success &= self.put(f"{prefix}observability/tracing", str(obs.tracing).lower())
        
        if router.tls:
            success &= self.put(f"{prefix}tls", "true")
            cert_resolver = self._extract_tls_cert_resolver(router.tls)
            if cert_resolver:
                success &= self.put(f"{prefix}tls/certresolver", cert_resolver)

            options = self._extract_tls_options(router.tls)
            if options:
                success &= self.put(f"{prefix}tls/options", options)

            domains = self._extract_tls_domains(router.tls)
            for i, domain in enumerate(domains):
                if hasattr(domain, 'name'):
                    main = getattr(domain, 'name', '')
                    sans = getattr(domain, 'sans', []) or []
                elif isinstance(domain, dict):
                    main = domain.get('name') or domain.get('main', '')
                    sans = domain.get('sans', []) or []
                else:
                    continue

                if main:
                    success &= self.put(f"{prefix}tls/domains/{i}/main", str(main))
                if isinstance(sans, list):
                    for j, san in enumerate(sans):
                        success &= self.put(f"{prefix}tls/domains/{i}/sans/{j}", str(san))
        
        return success
    
    def delete_http_router(self, name: str) -> bool:
        """
        Delete HTTP router from etcd.
        
        Args:
            name: Router name
            
        Returns:
            True on success
        """
        return self.delete_prefix(f"traefik/http/routers/{name}/")
    
    # HTTP Service Operations
    
    def get_http_service(self, name: str) -> Optional[Service]:
        """
        Get HTTP service by name with full KV parsing.
        
        Args:
            name: Service name
            
        Returns:
            Service object if found, None otherwise
        """
        prefix = f"traefik/http/services/{name}/"
        kvs = self.get_prefix(prefix)
        
        if not kvs:
            return None
        
        # Determine service type from keys
        has_lb = any(k.replace(prefix, '').startswith('loadbalancer/') for k in kvs)
        has_weighted = any(k.replace(prefix, '').startswith('weighted/') for k in kvs)
        has_mirroring = any(k.replace(prefix, '').startswith('mirroring/') for k in kvs)
        has_failover = any(k.replace(prefix, '').startswith('failover/') for k in kvs)
        
        service = Service(name=name)
        
        if has_lb:
            service.type = ServiceType.LOAD_BALANCER
            lb = LoadBalancerService()
            
            # Parse servers
            server_map: Dict[int, Dict[str, Any]] = {}
            for key, value in kvs.items():
                field = key.replace(prefix, '')
                if field.startswith('loadbalancer/servers/'):
                    rest = field.replace('loadbalancer/servers/', '')
                    parts = rest.split('/', 1)
                    if len(parts) == 2:
                        try:
                            idx = int(parts[0])
                        except ValueError:
                            continue
                        if idx not in server_map:
                            server_map[idx] = {}
                        server_map[idx][parts[1]] = value
            
            for idx in sorted(server_map.keys()):
                sd = server_map[idx]
                lb.servers.append(Server(
                    url=sd.get('url', ''),
                    weight=int(sd.get('weight', 1)),
                    preserve_path=str(sd.get('preservePath', 'false')).lower() == 'true',
                ))
            
            # passHostHeader
            pval = kvs.get(f"{prefix}loadbalancer/passhostheader")
            if pval is not None:
                lb.pass_host_header = pval.lower() == 'true'
            
            # serversTransport
            st = kvs.get(f"{prefix}loadbalancer/serverstransport")
            if st:
                lb.servers_transport = st
            
            # responseForwarding
            rf = kvs.get(f"{prefix}loadbalancer/responseforwarding/flushinterval")
            if rf:
                lb.response_forwarding_flush_interval = rf
            
            # Health check
            hc_prefix = f"{prefix}loadbalancer/healthcheck/"
            hc_kvs = {k.replace(hc_prefix, ''): v for k, v in kvs.items() if k.startswith(hc_prefix)}
            if hc_kvs:
                hc = HealthCheck()
                if 'path' in hc_kvs:
                    hc.path = hc_kvs['path']
                if 'interval' in hc_kvs:
                    hc.interval = hc_kvs['interval']
                if 'timeout' in hc_kvs:
                    hc.timeout = hc_kvs['timeout']
                if 'scheme' in hc_kvs:
                    hc.scheme = hc_kvs['scheme']
                if 'port' in hc_kvs:
                    try:
                        hc.port = int(hc_kvs['port'])
                    except ValueError:
                        pass
                if 'hostname' in hc_kvs:
                    hc.hostname = hc_kvs['hostname']
                if 'method' in hc_kvs:
                    hc.method = hc_kvs['method']
                if 'status' in hc_kvs:
                    try:
                        hc.status = int(hc_kvs['status'])
                    except ValueError:
                        pass
                # Headers
                for hk, hv in hc_kvs.items():
                    if hk.startswith('headers/'):
                        header_name = hk.replace('headers/', '')
                        hc.headers[header_name] = hv
                lb.health_check = hc
            
            # Sticky cookie
            sticky_prefix = f"{prefix}loadbalancer/sticky/cookie/"
            sticky_kvs = {k.replace(sticky_prefix, ''): v for k, v in kvs.items() if k.startswith(sticky_prefix)}
            if sticky_kvs or kvs.get(f"{prefix}loadbalancer/sticky"):
                sc = StickyCookie()
                if 'name' in sticky_kvs:
                    sc.name = sticky_kvs['name']
                if 'secure' in sticky_kvs:
                    sc.secure = sticky_kvs['secure'].lower() == 'true'
                if 'httponly' in sticky_kvs:
                    sc.http_only = sticky_kvs['httponly'].lower() == 'true'
                if 'samesite' in sticky_kvs:
                    sc.same_site = sticky_kvs['samesite']
                if 'maxage' in sticky_kvs:
                    try:
                        sc.max_age = int(sticky_kvs['maxage'])
                    except ValueError:
                        pass
                if 'path' in sticky_kvs:
                    sc.path = sticky_kvs['path']
                lb.sticky = sc
            
            service.load_balancer = lb
        
        elif has_weighted:
            service.type = ServiceType.WEIGHTED
            ws_map: Dict[int, Dict[str, str]] = {}
            for key, value in kvs.items():
                field = key.replace(prefix, '')
                if field.startswith('weighted/services/'):
                    rest = field.replace('weighted/services/', '')
                    parts = rest.split('/', 1)
                    if len(parts) == 2:
                        try:
                            idx = int(parts[0])
                        except ValueError:
                            continue
                        if idx not in ws_map:
                            ws_map[idx] = {}
                        ws_map[idx][parts[1]] = value
            for idx in sorted(ws_map.keys()):
                wd = ws_map[idx]
                service.weighted_services.append(WeightedService(
                    name=wd.get('name', ''),
                    weight=int(wd.get('weight', 100)),
                ))
            # Weighted sticky
            ws_prefix = f"{prefix}weighted/sticky/cookie/"
            ws_sticky = {k.replace(ws_prefix, ''): v for k, v in kvs.items() if k.startswith(ws_prefix)}
            if ws_sticky:
                sc = StickyCookie()
                if 'name' in ws_sticky:
                    sc.name = ws_sticky['name']
                if 'secure' in ws_sticky:
                    sc.secure = ws_sticky['secure'].lower() == 'true'
                if 'httpOnly' in ws_sticky:
                    sc.http_only = ws_sticky['httpOnly'].lower() == 'true'
                if 'samesite' in ws_sticky:
                    sc.same_site = ws_sticky['samesite']
                if 'maxage' in ws_sticky:
                    try:
                        sc.max_age = int(ws_sticky['maxage'])
                    except ValueError:
                        pass
                service.weighted_sticky = sc
        
        elif has_mirroring:
            service.type = ServiceType.MIRRORING
            ms = kvs.get(f"{prefix}mirroring/service", '')
            service.mirroring_service = ms
            mirror_map: Dict[int, Dict[str, str]] = {}
            for key, value in kvs.items():
                field = key.replace(prefix, '')
                if field.startswith('mirroring/mirrors/'):
                    rest = field.replace('mirroring/mirrors/', '')
                    parts = rest.split('/', 1)
                    if len(parts) == 2:
                        try:
                            idx = int(parts[0])
                        except ValueError:
                            continue
                        if idx not in mirror_map:
                            mirror_map[idx] = {}
                        mirror_map[idx][parts[1]] = value
            for idx in sorted(mirror_map.keys()):
                md = mirror_map[idx]
                service.mirrors.append(MirrorService(
                    name=md.get('name', ''),
                    percent=int(md.get('percent', 100)),
                ))
        
        elif has_failover:
            service.type = ServiceType.FAILOVER
            service.failover = FailoverService(
                service=kvs.get(f"{prefix}failover/service", ''),
                fallback=kvs.get(f"{prefix}failover/fallback", ''),
            )
        
        return service
    
    def put_http_service(self, service: Service) -> bool:
        """
        Save full HTTP service to etcd (loadBalancer / weighted / mirroring / failover).
        
        Args:
            service: Service object
            
        Returns:
            True on success
        """
        prefix = f"traefik/http/services/{service.name}/"
        self.delete_prefix(prefix)
        
        success = True
        
        if service.type == ServiceType.LOAD_BALANCER and service.load_balancer:
            lb = service.load_balancer
            for i, server in enumerate(lb.servers):
                success &= self.put(f"{prefix}loadbalancer/servers/{i}/url", server.url)
                if server.weight != 1:
                    success &= self.put(f"{prefix}loadbalancer/servers/{i}/weight", str(server.weight))
                if server.preserve_path:
                    success &= self.put(f"{prefix}loadbalancer/servers/{i}/preservePath", "true")
            
            if not lb.pass_host_header:
                success &= self.put(f"{prefix}loadbalancer/passhostheader", "false")
            
            if lb.servers_transport:
                success &= self.put(f"{prefix}loadbalancer/serverstransport", lb.servers_transport)
            
            if lb.response_forwarding_flush_interval and lb.response_forwarding_flush_interval != "100ms":
                success &= self.put(f"{prefix}loadbalancer/responseforwarding/flushinterval", lb.response_forwarding_flush_interval)
            
            if lb.health_check:
                hc = lb.health_check
                hcp = f"{prefix}loadbalancer/healthcheck/"
                if hc.path:
                    success &= self.put(f"{hcp}path", hc.path)
                if hc.interval:
                    success &= self.put(f"{hcp}interval", hc.interval)
                if hc.timeout:
                    success &= self.put(f"{hcp}timeout", hc.timeout)
                if hc.scheme:
                    success &= self.put(f"{hcp}scheme", hc.scheme)
                if hc.port:
                    success &= self.put(f"{hcp}port", str(hc.port))
                if hc.hostname:
                    success &= self.put(f"{hcp}hostname", hc.hostname)
                if hc.method and hc.method != "GET":
                    success &= self.put(f"{hcp}method", hc.method)
                if hc.status:
                    success &= self.put(f"{hcp}status", str(hc.status))
                for hk, hv in hc.headers.items():
                    success &= self.put(f"{hcp}headers/{hk}", hv)
            
            if lb.sticky:
                sc = lb.sticky
                success &= self.put(f"{prefix}loadbalancer/sticky", "true")
                scp = f"{prefix}loadbalancer/sticky/cookie/"
                if sc.name:
                    success &= self.put(f"{scp}name", sc.name)
                success &= self.put(f"{scp}secure", str(sc.secure).lower())
                success &= self.put(f"{scp}httponly", str(sc.http_only).lower())
                if sc.same_site:
                    success &= self.put(f"{scp}samesite", sc.same_site)
                if sc.max_age:
                    success &= self.put(f"{scp}maxage", str(sc.max_age))
                if sc.path:
                    success &= self.put(f"{scp}path", sc.path)
        
        elif service.type == ServiceType.WEIGHTED:
            for i, ws in enumerate(service.weighted_services):
                success &= self.put(f"{prefix}weighted/services/{i}/name", ws.name)
                success &= self.put(f"{prefix}weighted/services/{i}/weight", str(ws.weight))
            if service.weighted_sticky:
                sc = service.weighted_sticky
                scp = f"{prefix}weighted/sticky/cookie/"
                if sc.name:
                    success &= self.put(f"{scp}name", sc.name)
                success &= self.put(f"{scp}secure", str(sc.secure).lower())
                success &= self.put(f"{scp}httpOnly", str(sc.http_only).lower())
                if sc.same_site:
                    success &= self.put(f"{scp}samesite", sc.same_site)
                if sc.max_age:
                    success &= self.put(f"{scp}maxage", str(sc.max_age))
        
        elif service.type == ServiceType.MIRRORING:
            if service.mirroring_service:
                success &= self.put(f"{prefix}mirroring/service", service.mirroring_service)
            for i, mirror in enumerate(service.mirrors):
                success &= self.put(f"{prefix}mirroring/mirrors/{i}/name", mirror.name)
                success &= self.put(f"{prefix}mirroring/mirrors/{i}/percent", str(mirror.percent))
        
        elif service.type == ServiceType.FAILOVER and service.failover:
            fo = service.failover
            if fo.service:
                success &= self.put(f"{prefix}failover/service", fo.service)
            if fo.fallback:
                success &= self.put(f"{prefix}failover/fallback", fo.fallback)
            if fo.health_check:
                success &= self.put(f"{prefix}failover/healthcheck", "{}")
        
        return success
    
    def list_http_services(self) -> List[str]:
        """
        List all HTTP service names.
        
        Returns:
            List of service names
        """
        kvs = self.get_prefix("traefik/http/services/")
        
        services = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                services.add(parts[3])
        
        return sorted(list(services))
    
    def put_http_service_simple(self, name: str, url: str) -> bool:
        """
        Create a simple HTTP service with one server.
        
        Args:
            name: Service name
            url: Server URL
            
        Returns:
            True on success
        """
        prefix = f"traefik/http/services/{name}/"
        self.delete_prefix(prefix)
        return self.put(f"{prefix}loadbalancer/servers/0/url", url)
    
    def delete_http_service(self, name: str) -> bool:
        """
        Delete HTTP service from etcd.
        
        Args:
            name: Service name
            
        Returns:
            True on success
        """
        return self.delete_prefix(f"traefik/http/services/{name}/")
    
    # HTTP Middleware Operations
    
    def get_http_middleware(self, name: str) -> Optional[Tuple[MiddlewareType, Any]]:
        """
        Get HTTP middleware by name.
        
        Args:
            name: Middleware name
            
        Returns:
            Tuple of (MiddlewareType, middleware_object) if found, None otherwise
        """
        prefix = f"traefik/http/middlewares/{name}/"
        kvs = self.get_prefix(prefix)
        
        if not kvs:
            return None
        
        def _to_bool(value: Any, default: bool = False) -> bool:
            if value is None:
                return default
            return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

        for key in kvs.keys():
            parts = key.replace(prefix, '').split('/')
            if not parts:
                continue

            type_name = parts[0]
            try:
                mw_type = MiddlewareType(type_name)
            except ValueError:
                continue

            type_prefix = f"{prefix}{mw_type.value}/"
            config_pairs = {
                k.replace(type_prefix, ''): v
                for k, v in kvs.items()
                if k.startswith(type_prefix)
            }

            if mw_type == MiddlewareType.ADD_PREFIX:
                return (mw_type, {'prefix': config_pairs.get('prefix', '')})

            if mw_type == MiddlewareType.STRIP_PREFIX:
                indexed_prefixes = {}
                for sub_key, sub_value in config_pairs.items():
                    if sub_key == 'prefixes':
                        indexed_prefixes[0] = sub_value
                    elif sub_key.startswith('prefixes/'):
                        _, _, maybe_index = sub_key.partition('/')
                        try:
                            indexed_prefixes[int(maybe_index)] = sub_value
                        except ValueError:
                            continue

                prefixes = [
                    value for _, value in sorted(indexed_prefixes.items(), key=lambda item: item[0])
                ]
                force_slash = config_pairs.get('forceSlash', config_pairs.get('force_slash', 'true'))
                return (
                    mw_type,
                    {
                        'prefixes': prefixes,
                        'force_slash': _to_bool(force_slash, default=True),
                    },
                )

            if mw_type == MiddlewareType.REDIRECT_SCHEME:
                return (
                    mw_type,
                    {
                        'scheme': config_pairs.get('scheme', 'https'),
                        'port': config_pairs.get('port', ''),
                        'permanent': _to_bool(config_pairs.get('permanent', 'true'), default=True),
                    },
                )

            if mw_type == MiddlewareType.RATE_LIMIT:
                average = config_pairs.get('average', '100')
                burst = config_pairs.get('burst', '50')
                ip_depth_raw = config_pairs.get('sourceCriterion/ipStrategy/depth', '0')

                try:
                    average_int = int(average)
                except (TypeError, ValueError):
                    average_int = 100

                try:
                    burst_int = int(burst)
                except (TypeError, ValueError):
                    burst_int = 50

                try:
                    ip_depth = int(ip_depth_raw)
                except (TypeError, ValueError):
                    ip_depth = 0

                excluded_ips = [
                    value
                    for sub_key, value in sorted(config_pairs.items())
                    if sub_key.startswith('sourceCriterion/ipStrategy/excludedIPs/')
                ]

                return (
                    mw_type,
                    {
                        'average': average_int,
                        'burst': burst_int,
                        'period': config_pairs.get('period', '1s'),
                        'use_request_host': _to_bool(
                            config_pairs.get('sourceCriterion/requestHost', 'false'),
                            default=False,
                        ),
                        'use_request_header': config_pairs.get('sourceCriterion/requestHeaderName', ''),
                        'use_ip_strategy': (
                            'sourceCriterion/ipStrategy/depth' in config_pairs
                            or bool(excluded_ips)
                        ),
                        'ip_depth': ip_depth,
                        'excluded_ips': excluded_ips,
                    },
                )

            if mw_type == MiddlewareType.BASIC_AUTH:
                indexed_users = {}
                for sub_key, sub_value in config_pairs.items():
                    if sub_key == 'users':
                        indexed_users[0] = sub_value
                    elif sub_key.startswith('users/'):
                        _, _, maybe_index = sub_key.partition('/')
                        try:
                            indexed_users[int(maybe_index)] = sub_value
                        except ValueError:
                            continue

                users = [
                    value for _, value in sorted(indexed_users.items(), key=lambda item: item[0])
                ]

                remove_header = config_pairs.get(
                    'removeHeader',
                    config_pairs.get('remove_header', 'false')
                )

                return (
                    mw_type,
                    {
                        'users': users,
                        'realm': config_pairs.get('realm', 'Restricted'),
                        'remove_header': _to_bool(remove_header, default=False),
                    },
                )

            # --- Full coverage for remaining middleware types ---

            if mw_type == MiddlewareType.HEADERS:
                result = {}
                for ck, cv in config_pairs.items():
                    if ck.startswith('customRequestHeaders/'):
                        result.setdefault('custom_request_headers', {})[ck.split('/', 1)[1]] = cv
                    elif ck.startswith('customResponseHeaders/'):
                        result.setdefault('custom_response_headers', {})[ck.split('/', 1)[1]] = cv
                    elif ck == 'sslRedirect':
                        result['ssl_redirect'] = _to_bool(cv)
                    elif ck == 'stsSeconds':
                        try: result['sts_seconds'] = int(cv)
                        except ValueError: pass
                    elif ck == 'stsIncludeSubdomains':
                        result['sts_include_subdomains'] = _to_bool(cv)
                    elif ck == 'stsPreload':
                        result['sts_preload'] = _to_bool(cv)
                    elif ck == 'forceSTSHeader':
                        result['force_sts_header'] = _to_bool(cv)
                    elif ck == 'frameDeny':
                        result['frame_deny'] = _to_bool(cv)
                    elif ck == 'customFrameOptionsValue':
                        result['custom_frame_options_value'] = cv
                    elif ck == 'contentTypeNosniff':
                        result['content_type_nosniff'] = _to_bool(cv)
                    elif ck == 'browserXssFilter':
                        result['browser_xss_filter'] = _to_bool(cv)
                    elif ck == 'contentSecurityPolicy':
                        result['content_security_policy'] = cv
                    elif ck == 'referrerPolicy':
                        result['referrer_policy'] = cv
                    elif ck == 'accessControlAllowCredentials':
                        result['access_control_allow_credentials'] = _to_bool(cv)
                    elif ck.startswith('accessControlAllowHeaders/'):
                        result.setdefault('access_control_allow_headers', []).append(cv)
                    elif ck.startswith('accessControlAllowMethods/'):
                        result.setdefault('access_control_allow_methods', []).append(cv)
                    elif ck.startswith('accessControlAllowOriginList/'):
                        result.setdefault('access_control_allow_origin_list', []).append(cv)
                    elif ck.startswith('accessControlExposeHeaders/'):
                        result.setdefault('access_control_expose_headers', []).append(cv)
                    elif ck == 'accessControlMaxAge':
                        try: result['access_control_max_age'] = int(cv)
                        except ValueError: pass
                return (mw_type, result)

            if mw_type == MiddlewareType.CIRCUIT_BREAKER:
                return (mw_type, {
                    'expression': config_pairs.get('expression', ''),
                    'checkPeriod': config_pairs.get('checkPeriod', '10s'),
                    'fallbackDuration': config_pairs.get('fallbackDuration', '30s'),
                    'recoveryDuration': config_pairs.get('recoveryDuration', '10s'),
                })

            if mw_type == MiddlewareType.RETRY:
                attempts = config_pairs.get('attempts', '4')
                try: attempts_int = int(attempts)
                except ValueError: attempts_int = 4
                return (mw_type, {
                    'attempts': attempts_int,
                    'initialInterval': config_pairs.get('initialInterval', '100ms'),
                })

            if mw_type == MiddlewareType.COMPRESS:
                excluded = [v for k, v in sorted(config_pairs.items()) if k.startswith('excludedContentTypes/')]
                min_bytes = config_pairs.get('minResponseBodyBytes', '1024')
                try: min_bytes_int = int(min_bytes)
                except ValueError: min_bytes_int = 1024
                return (mw_type, {
                    'excludedContentTypes': excluded,
                    'minResponseBodyBytes': min_bytes_int,
                })

            if mw_type == MiddlewareType.DIGEST_AUTH:
                users = self._collect_indexed_list(config_pairs, 'users')
                return (mw_type, {
                    'users': users,
                    'realm': config_pairs.get('realm', 'Restricted'),
                    'removeHeader': _to_bool(config_pairs.get('removeHeader', 'false')),
                    'headerField': config_pairs.get('headerField', ''),
                })

            if mw_type == MiddlewareType.FORWARD_AUTH:
                return (mw_type, {
                    'address': config_pairs.get('address', ''),
                    'trustForwardHeader': _to_bool(config_pairs.get('trustForwardHeader', 'false')),
                    'authResponseHeaders': [v for k, v in sorted(config_pairs.items()) if k.startswith('authResponseHeaders/')],
                    'authResponseHeadersRegex': config_pairs.get('authResponseHeadersRegex', ''),
                    'authRequestHeaders': [v for k, v in sorted(config_pairs.items()) if k.startswith('authRequestHeaders/')],
                    'tls/ca': config_pairs.get('tls/ca', ''),
                    'tls/cert': config_pairs.get('tls/cert', ''),
                    'tls/key': config_pairs.get('tls/key', ''),
                    'tls/insecureSkipVerify': _to_bool(config_pairs.get('tls/insecureSkipVerify', 'false')),
                })

            if mw_type == MiddlewareType.IP_WHITELIST:
                source_range = [v for k, v in sorted(config_pairs.items()) if k.startswith('sourceRange/')]
                excluded_ips = [v for k, v in sorted(config_pairs.items()) if k.startswith('ipStrategy/excludedIPs/')]
                ip_depth = config_pairs.get('ipStrategy/depth', '0')
                try: ip_depth_int = int(ip_depth)
                except ValueError: ip_depth_int = 0
                return (mw_type, {
                    'sourceRange': source_range,
                    'ipStrategy': {'depth': ip_depth_int, 'excludedIPs': excluded_ips},
                })

            if mw_type == MiddlewareType.REDIRECT_REGEX:
                return (mw_type, {
                    'regex': config_pairs.get('regex', ''),
                    'replacement': config_pairs.get('replacement', ''),
                    'permanent': _to_bool(config_pairs.get('permanent', 'false')),
                })

            if mw_type == MiddlewareType.CHAIN:
                middlewares = [v for k, v in sorted(config_pairs.items()) if k.startswith('middlewares/')]
                return (mw_type, {'middlewares': middlewares})

            if mw_type == MiddlewareType.BUFFERING:
                def _int(val, default):
                    try: return int(val)
                    except (TypeError, ValueError): return default
                return (mw_type, {
                    'maxRequestBodyBytes': _int(config_pairs.get('maxRequestBodyBytes'), 2097152),
                    'memRequestBodyBytes': _int(config_pairs.get('memRequestBodyBytes'), 1048576),
                    'maxResponseBodyBytes': _int(config_pairs.get('maxResponseBodyBytes'), 2097152),
                    'memResponseBodyBytes': _int(config_pairs.get('memResponseBodyBytes'), 1048576),
                    'retryExpression': config_pairs.get('retryExpression', ''),
                })

            if mw_type == MiddlewareType.IN_FLIGHT_REQ:
                amount = config_pairs.get('amount', '10')
                try: amount_int = int(amount)
                except ValueError: amount_int = 10
                ip_depth_raw = config_pairs.get('sourceCriterion/ipStrategy/depth', '0')
                try: ip_depth = int(ip_depth_raw)
                except ValueError: ip_depth = 0
                return (mw_type, {
                    'amount': amount_int,
                    'sourceCriterion': {
                        'ipStrategy': {'depth': ip_depth},
                        'requestHost': _to_bool(config_pairs.get('sourceCriterion/requestHost', 'false')),
                    },
                })

            if mw_type == MiddlewareType.PASS_TLS_CLIENT_CERT:
                return (mw_type, config_pairs)

            if mw_type == MiddlewareType.CONTENT_TYPE:
                return (mw_type, config_pairs)

            if mw_type == MiddlewareType.GRPC_WEB:
                return (mw_type, {
                    'allowOrigins': [v for k, v in sorted(config_pairs.items()) if k.startswith('allowOrigins/')],
                })

            if mw_type == MiddlewareType.STRIP_PREFIX_REGEX:
                regex_list = [v for k, v in sorted(config_pairs.items()) if k.startswith('regex/')]
                return (mw_type, {'regex': regex_list})

            if mw_type == MiddlewareType.REPLACE_PATH:
                return (mw_type, {'path': config_pairs.get('path', '')})

            if mw_type == MiddlewareType.REPLACE_PATH_REGEX:
                return (mw_type, {
                    'regex': config_pairs.get('regex', ''),
                    'replacement': config_pairs.get('replacement', ''),
                })

            return (mw_type, config_pairs)
        
        return None
    
    def _collect_indexed_list(self, pairs: Dict[str, str], key: str) -> List[str]:
        """Collect indexed list values from config pairs (key or key/0, key/1, ...)."""
        indexed = {}
        for k, v in pairs.items():
            if k == key:
                indexed[0] = v
            elif k.startswith(f"{key}/"):
                _, _, idx = k.partition('/')
                try:
                    indexed[int(idx)] = v
                except ValueError:
                    continue
        return [v for _, v in sorted(indexed.items())]
    
    def list_http_middlewares(self) -> List[str]:
        """
        List all HTTP middleware names.
        
        Returns:
            List of middleware names
        """
        kvs = self.get_prefix("traefik/http/middlewares/")
        
        middlewares = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                middlewares.add(parts[3])
        
        return sorted(list(middlewares))
    
    def put_http_middleware(self, name: str, middleware_type: MiddlewareType, config: Any) -> bool:
        """
        Save HTTP middleware to etcd.
        
        Args:
            name: Middleware name
            middleware_type: Type of middleware
            config: Middleware configuration object
            
        Returns:
            True on success
        """
        prefix = f"traefik/http/middlewares/{name}/{middleware_type.value}/"
        self.delete_prefix(f"traefik/http/middlewares/{name}/")
        
        # Convert middleware config to etcd keys
        config_dict = self._middleware_config_to_etcd_dict(middleware_type, config)
        
        success = True
        for key, value in self._flatten_dict(config_dict).items():
            full_key = f"{prefix}{key}"
            success &= self.put(full_key, str(value))
        
        return success

    def _middleware_config_to_etcd_dict(self, middleware_type: MiddlewareType, config: Any) -> Dict[str, Any]:
        """Build middleware payload with Traefik fields only."""
        raw = middleware_to_dict(config)

        if middleware_type == MiddlewareType.ADD_PREFIX:
            return {'prefix': raw.get('prefix', '')}

        if middleware_type == MiddlewareType.STRIP_PREFIX:
            return {
                'prefixes': list(raw.get('prefixes', []) or []),
                'forceSlash': bool(raw.get('force_slash', True)),
            }

        if middleware_type == MiddlewareType.REDIRECT_SCHEME:
            payload = {
                'scheme': raw.get('scheme', 'https'),
                'permanent': bool(raw.get('permanent', True)),
            }
            port = raw.get('port', '')
            if port:
                payload['port'] = str(port)
            return payload

        if middleware_type == MiddlewareType.RATE_LIMIT:
            payload = {
                'average': int(raw.get('average', 100)),
                'burst': int(raw.get('burst', 50)),
                'period': raw.get('period', '1s'),
            }

            source_criterion = {}
            if raw.get('use_request_host'):
                source_criterion['requestHost'] = True

            request_header_name = (raw.get('use_request_header') or '').strip()
            if request_header_name:
                source_criterion['requestHeaderName'] = request_header_name

            if raw.get('use_ip_strategy', True):
                ip_strategy = {'depth': int(raw.get('ip_depth', 0) or 0)}
                excluded_ips = list(raw.get('excluded_ips', []) or [])
                if excluded_ips:
                    ip_strategy['excludedIPs'] = excluded_ips
                source_criterion['ipStrategy'] = ip_strategy

            if source_criterion:
                payload['sourceCriterion'] = source_criterion

            return payload

        if middleware_type == MiddlewareType.BASIC_AUTH:
            payload = {
                'users': list(raw.get('users', []) or []),
                'realm': raw.get('realm', 'Restricted'),
                'removeHeader': bool(raw.get('remove_header', False)),
            }
            header_field = (raw.get('header_field') or '').strip()
            if header_field:
                payload['headerField'] = header_field
            return payload

        # --- Full coverage for remaining middleware types ---

        if middleware_type == MiddlewareType.HEADERS:
            payload = {}
            for hdr_key in ('customRequestHeaders', 'customResponseHeaders'):
                vals = raw.get(hdr_key) or raw.get(hdr_key.replace('H', '_h').replace('R', '_r').replace('C', '_c')) or {}
                if isinstance(vals, dict):
                    for k, v in vals.items():
                        payload[f'{hdr_key}/{k}'] = v
            bool_fields = [
                ('sslRedirect', 'ssl_redirect'), ('stsIncludeSubdomains', 'sts_include_subdomains'),
                ('stsPreload', 'sts_preload'), ('forceSTSHeader', 'force_sts_header'),
                ('frameDeny', 'frame_deny'), ('contentTypeNosniff', 'content_type_nosniff'),
                ('browserXssFilter', 'browser_xss_filter'),
                ('accessControlAllowCredentials', 'access_control_allow_credentials'),
            ]
            for traefik_key, python_key in bool_fields:
                val = raw.get(python_key) or raw.get(traefik_key)
                if val is not None:
                    payload[traefik_key] = str(bool(val)).lower()
            int_fields = [('stsSeconds', 'sts_seconds'), ('accessControlMaxAge', 'access_control_max_age')]
            for traefik_key, python_key in int_fields:
                val = raw.get(python_key) or raw.get(traefik_key)
                if val is not None:
                    payload[traefik_key] = str(int(val))
            str_fields = [
                ('customFrameOptionsValue', 'custom_frame_options_value'),
                ('contentSecurityPolicy', 'content_security_policy'),
                ('referrerPolicy', 'referrer_policy'),
            ]
            for traefik_key, python_key in str_fields:
                val = raw.get(python_key) or raw.get(traefik_key) or ''
                if val:
                    payload[traefik_key] = val
            list_fields = [
                ('accessControlAllowHeaders', 'access_control_allow_headers'),
                ('accessControlAllowMethods', 'access_control_allow_methods'),
                ('accessControlAllowOriginList', 'access_control_allow_origin_list'),
                ('accessControlExposeHeaders', 'access_control_expose_headers'),
            ]
            for traefik_key, python_key in list_fields:
                vals = raw.get(python_key) or raw.get(traefik_key) or []
                for i, v in enumerate(vals):
                    payload[f'{traefik_key}/{i}'] = v
            return payload

        if middleware_type == MiddlewareType.CIRCUIT_BREAKER:
            return {
                'expression': raw.get('expression', ''),
                'checkPeriod': raw.get('checkPeriod', raw.get('check_period', '10s')),
                'fallbackDuration': raw.get('fallbackDuration', raw.get('fallback_duration', '30s')),
                'recoveryDuration': raw.get('recoveryDuration', raw.get('recovery_duration', '10s')),
            }

        if middleware_type == MiddlewareType.RETRY:
            return {
                'attempts': str(int(raw.get('attempts', 4))),
                'initialInterval': raw.get('initialInterval', raw.get('initial_interval', '100ms')),
            }

        if middleware_type == MiddlewareType.COMPRESS:
            payload = {}
            excluded = raw.get('excludedContentTypes', raw.get('excluded_content_types', []))
            for i, v in enumerate(excluded or []):
                payload[f'excludedContentTypes/{i}'] = v
            min_bytes = raw.get('minResponseBodyBytes', raw.get('min_response_body_bytes'))
            if min_bytes is not None:
                payload['minResponseBodyBytes'] = str(int(min_bytes))
            return payload

        if middleware_type == MiddlewareType.DIGEST_AUTH:
            payload = {
                'realm': raw.get('realm', 'Restricted'),
                'removeHeader': str(bool(raw.get('remove_header', raw.get('removeHeader', False)))).lower(),
            }
            users = raw.get('users', [])
            for i, u in enumerate(users or []):
                payload[f'users/{i}'] = u
            header_field = raw.get('header_field', raw.get('headerField', ''))
            if header_field:
                payload['headerField'] = header_field
            return payload

        if middleware_type == MiddlewareType.FORWARD_AUTH:
            payload = {
                'address': raw.get('address', ''),
                'trustForwardHeader': str(bool(raw.get('trustForwardHeader', raw.get('trust_forward_header', False)))).lower(),
            }
            for list_key in ('authResponseHeaders', 'authRequestHeaders'):
                vals = raw.get(list_key, raw.get(list_key.replace('H', '_h').replace('R', '_r'), []))
                for i, v in enumerate(vals or []):
                    payload[f'{list_key}/{i}'] = v
            regex = raw.get('authResponseHeadersRegex', raw.get('auth_response_headers_regex', ''))
            if regex:
                payload['authResponseHeadersRegex'] = regex
            for tls_key in ('tls/ca', 'tls/cert', 'tls/key'):
                val = raw.get(tls_key, '')
                if val:
                    payload[tls_key] = val
            insecure = raw.get('tls/insecureSkipVerify', False)
            if insecure:
                payload['tls/insecureSkipVerify'] = str(bool(insecure)).lower()
            return payload

        if middleware_type == MiddlewareType.IP_WHITELIST:
            payload = {}
            source_range = raw.get('sourceRange', raw.get('source_range', []))
            for i, v in enumerate(source_range or []):
                payload[f'sourceRange/{i}'] = v
            ip_strategy = raw.get('ipStrategy', raw.get('ip_strategy', {})) or {}
            depth = ip_strategy.get('depth', 0)
            if depth:
                payload['ipStrategy/depth'] = str(int(depth))
            excluded = ip_strategy.get('excludedIPs', ip_strategy.get('excluded_ips', []))
            for i, v in enumerate(excluded or []):
                payload[f'ipStrategy/excludedIPs/{i}'] = v
            return payload

        if middleware_type == MiddlewareType.REDIRECT_REGEX:
            return {
                'regex': raw.get('regex', ''),
                'replacement': raw.get('replacement', ''),
                'permanent': str(bool(raw.get('permanent', False))).lower(),
            }

        if middleware_type == MiddlewareType.CHAIN:
            payload = {}
            middlewares = raw.get('middlewares', [])
            for i, m in enumerate(middlewares or []):
                payload[f'middlewares/{i}'] = m
            return payload

        if middleware_type == MiddlewareType.BUFFERING:
            return {
                'maxRequestBodyBytes': str(int(raw.get('maxRequestBodyBytes', raw.get('max_request_body_bytes', 2097152)))),
                'memRequestBodyBytes': str(int(raw.get('memRequestBodyBytes', raw.get('mem_request_body_bytes', 1048576)))),
                'maxResponseBodyBytes': str(int(raw.get('maxResponseBodyBytes', raw.get('max_response_body_bytes', 2097152)))),
                'memResponseBodyBytes': str(int(raw.get('memResponseBodyBytes', raw.get('mem_response_body_bytes', 1048576)))),
                'retryExpression': raw.get('retryExpression', raw.get('retry_expression', '')),
            }

        if middleware_type == MiddlewareType.IN_FLIGHT_REQ:
            payload = {'amount': str(int(raw.get('amount', 10)))}
            sc = raw.get('sourceCriterion', raw.get('source_criterion', {})) or {}
            ip_strat = sc.get('ipStrategy', sc.get('ip_strategy', {})) or {}
            depth = ip_strat.get('depth', 0)
            if depth:
                payload['sourceCriterion/ipStrategy/depth'] = str(int(depth))
            if sc.get('requestHost', sc.get('request_host', False)):
                payload['sourceCriterion/requestHost'] = 'true'
            return payload

        if middleware_type == MiddlewareType.PASS_TLS_CLIENT_CERT:
            payload = {}
            for k, v in raw.items():
                if k not in ('name', 'type', 'enabled'):
                    payload[k] = str(v)
            return payload

        if middleware_type == MiddlewareType.CONTENT_TYPE:
            return {}

        if middleware_type == MiddlewareType.GRPC_WEB:
            payload = {}
            origins = raw.get('allowOrigins', raw.get('allow_origins', []))
            for i, v in enumerate(origins or []):
                payload[f'allowOrigins/{i}'] = v
            return payload

        if middleware_type == MiddlewareType.STRIP_PREFIX_REGEX:
            payload = {}
            regexes = raw.get('regex', [])
            for i, v in enumerate(regexes or []):
                payload[f'regex/{i}'] = v
            return payload

        if middleware_type == MiddlewareType.REPLACE_PATH:
            return {'path': raw.get('path', '')}

        if middleware_type == MiddlewareType.REPLACE_PATH_REGEX:
            return {
                'regex': raw.get('regex', ''),
                'replacement': raw.get('replacement', ''),
            }

        return {k: v for k, v in raw.items() if k not in {'name', 'type', 'enabled'}}
    
    def delete_http_middleware(self, name: str) -> bool:
        """
        Delete HTTP middleware from etcd.
        
        Args:
            name: Middleware name
            
        Returns:
            True on success
        """
        return self.delete_prefix(f"traefik/http/middlewares/{name}/")
    
    # TCP Router Operations
    
    def list_tcp_routers(self) -> List[str]:
        """List all TCP router names."""
        kvs = self.get_prefix("traefik/tcp/routers/")
        routers = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                routers.add(parts[3])
        return sorted(list(routers))

    def get_tcp_router(self, name: str) -> Optional[TCPRouter]:
        """Get a TCP router by name with all KV fields."""
        prefix = f"traefik/tcp/routers/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        data = {
            'name': name, 'rule': '', 'service': '',
            'entrypoints': [], 'middlewares': [], 'priority': 0, 'tls': None,
        }
        tls_data = {}

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field == 'rule':
                data['rule'] = value
            elif field == 'service':
                data['service'] = value
            elif field == 'entrypoints' or field.startswith('entrypoints/'):
                data['entrypoints'].append(value)
            elif field == 'middlewares' or field.startswith('middlewares/'):
                data['middlewares'].append(value)
            elif field == 'priority':
                try: data['priority'] = int(value)
                except ValueError: pass
            elif field.startswith('tls'):
                sf = field.replace('tls/', '').replace('tls', '')
                if sf == '' or sf == 'tls':
                    tls_data['enabled'] = True
                elif sf == 'certResolver' or sf == 'certresolver':
                    tls_data['cert_resolver'] = value
                    tls_data['enabled'] = True
                elif sf == 'options':
                    tls_data['options'] = value
                    tls_data['enabled'] = True
                elif sf == 'passthrough':
                    tls_data['passthrough'] = value.lower() == 'true'
                    tls_data['enabled'] = True
                elif sf.startswith('domains/'):
                    tls_data['enabled'] = True

        if tls_data.get('enabled'):
            data['tls'] = TLSConfig(
                cert_resolver=tls_data.get('cert_resolver', ''),
                options=tls_data.get('options', ''),
                domains=[],
            )
        if tls_data.get('passthrough'):
            data['tls_passthrough'] = True

        return TCPRouter(**data)

    def put_tcp_router(self, router: 'TCPRouter') -> bool:
        """Write a TCP router to etcd."""
        prefix = f"traefik/tcp/routers/{router.name}/"
        self.delete_prefix(prefix)
        success = True
        success &= self.put(f"{prefix}rule", router.rule)
        success &= self.put(f"{prefix}service", router.service)
        for i, ep in enumerate(router.entrypoints or []):
            success &= self.put(f"{prefix}entrypoints/{i}", ep)
        for i, mw in enumerate(router.middlewares or []):
            success &= self.put(f"{prefix}middlewares/{i}", mw)
        if router.priority:
            success &= self.put(f"{prefix}priority", str(router.priority))
        if router.tls:
            success &= self.put(f"{prefix}tls", "true")
            cr = self._extract_tls_cert_resolver(router.tls)
            if cr:
                success &= self.put(f"{prefix}tls/certResolver", cr)
            opts = self._extract_tls_options(router.tls)
            if opts:
                success &= self.put(f"{prefix}tls/options", opts)
            if hasattr(router, 'tls_passthrough') and router.tls_passthrough:
                success &= self.put(f"{prefix}tls/passthrough", "true")
            domains = self._extract_tls_domains(router.tls)
            for i, d in enumerate(domains or []):
                if isinstance(d, dict):
                    if d.get('main'):
                        success &= self.put(f"{prefix}tls/domains/{i}/main", d['main'])
                    for j, san in enumerate(d.get('sans', [])):
                        success &= self.put(f"{prefix}tls/domains/{i}/sans/{j}", san)
        return success

    def delete_tcp_router(self, name: str) -> bool:
        """Delete TCP router from etcd."""
        return self.delete_prefix(f"traefik/tcp/routers/{name}/")

    # TCP Service Operations

    def list_tcp_services(self) -> List[str]:
        """List all TCP service names."""
        kvs = self.get_prefix("traefik/tcp/services/")
        services = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                services.add(parts[3])
        return sorted(list(services))

    def get_tcp_service(self, name: str) -> Optional[TCPService]:
        """Get a TCP service by name."""
        prefix = f"traefik/tcp/services/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        svc = TCPService(name=name, servers=[])

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field.startswith('loadBalancer/servers/'):
                parts = field.split('/')
                if len(parts) >= 4:
                    idx = int(parts[2])
                    while len(svc.servers) <= idx:
                        svc.servers.append(TCPServer(address=''))
                    attr = parts[3]
                    if attr == 'address':
                        svc.servers[idx].address = value
                    elif attr == 'tls':
                        svc.servers[idx].tls = value.lower() == 'true'
            elif field == 'loadBalancer/terminationDelay':
                try: svc.termination_delay = int(value)
                except ValueError: pass
            elif field == 'loadBalancer/proxyProtocol/version':
                try: svc.proxy_protocol_version = int(value)
                except ValueError: pass
            elif field == 'loadBalancer/serversTransport':
                svc.servers_transport = value
            elif field.startswith('weighted/'):
                svc.service_type = 'weighted'
                # Parse weighted TCP service
                if field.startswith('weighted/services/'):
                    parts = field.split('/')
                    if len(parts) >= 4:
                        idx = int(parts[2])
                        # Store in raw format - we mainly need the loadBalancer servers
                        pass

        return svc

    def put_tcp_service(self, service: TCPService) -> bool:
        """Write a TCP service to etcd."""
        prefix = f"traefik/tcp/services/{service.name}/"
        self.delete_prefix(prefix)
        success = True

        svc_type = getattr(service, 'service_type', 'loadBalancer') or 'loadBalancer'

        if svc_type == 'loadBalancer':
            for i, server in enumerate(service.servers or []):
                success &= self.put(f"{prefix}loadBalancer/servers/{i}/address", server.address)
                if hasattr(server, 'tls') and server.tls:
                    success &= self.put(f"{prefix}loadBalancer/servers/{i}/tls", "true")
            if hasattr(service, 'termination_delay') and service.termination_delay is not None:
                success &= self.put(f"{prefix}loadBalancer/terminationDelay", str(service.termination_delay))
            if hasattr(service, 'proxy_protocol_version') and service.proxy_protocol_version:
                success &= self.put(f"{prefix}loadBalancer/proxyProtocol/version", str(service.proxy_protocol_version))
            if hasattr(service, 'servers_transport') and service.servers_transport:
                success &= self.put(f"{prefix}loadBalancer/serversTransport", service.servers_transport)

        return success

    def delete_tcp_service(self, name: str) -> bool:
        """Delete TCP service from etcd."""
        return self.delete_prefix(f"traefik/tcp/services/{name}/")

    # TCP Middleware Operations

    def list_tcp_middlewares(self) -> List[str]:
        """List all TCP middleware names."""
        kvs = self.get_prefix("traefik/tcp/middlewares/")
        middlewares = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                middlewares.add(parts[3])
        return sorted(list(middlewares))

    def get_tcp_middleware(self, name: str) -> Optional[tuple]:
        """Get a TCP middleware by name. Returns (TCPMiddlewareType, config_dict) or None."""
        prefix = f"traefik/tcp/middlewares/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            parts = field.split('/')
            mw_type_str = parts[0]

            try:
                mw_type = TCPMiddlewareType(mw_type_str)
            except ValueError:
                continue

            config_pairs = {}
            for k, v in kvs.items():
                f = k.replace(prefix, '')
                if f.startswith(f"{mw_type_str}/"):
                    config_key = f.replace(f"{mw_type_str}/", '')
                    config_pairs[config_key] = v

            if mw_type == TCPMiddlewareType.IN_FLIGHT_CONN:
                amount = config_pairs.get('amount', '10')
                try: amount_int = int(amount)
                except ValueError: amount_int = 10
                return (mw_type, {'amount': amount_int})

            if mw_type == TCPMiddlewareType.IP_ALLOW_LIST:
                source_range = [v for k, v in sorted(config_pairs.items()) if k.startswith('sourceRange/')]
                return (mw_type, {'sourceRange': source_range})

            return (mw_type, config_pairs)

        return None

    def put_tcp_middleware(self, name: str, mw_type: 'TCPMiddlewareType', config: Dict) -> bool:
        """Write a TCP middleware to etcd."""
        prefix = f"traefik/tcp/middlewares/{name}/"
        self.delete_prefix(prefix)
        success = True

        type_name = mw_type.value

        if mw_type == TCPMiddlewareType.IN_FLIGHT_CONN:
            success &= self.put(f"{prefix}{type_name}/amount", str(config.get('amount', 10)))
        elif mw_type == TCPMiddlewareType.IP_ALLOW_LIST:
            for i, sr in enumerate(config.get('sourceRange', [])):
                success &= self.put(f"{prefix}{type_name}/sourceRange/{i}", sr)
        else:
            for k, v in config.items():
                success &= self.put(f"{prefix}{type_name}/{k}", str(v))

        return success

    def delete_tcp_middleware(self, name: str) -> bool:
        """Delete TCP middleware from etcd."""
        return self.delete_prefix(f"traefik/tcp/middlewares/{name}/")

    # UDP Router Operations
    
    def list_udp_routers(self) -> List[str]:
        """List all UDP router names."""
        kvs = self.get_prefix("traefik/udp/routers/")
        routers = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                routers.add(parts[3])
        return sorted(list(routers))

    def get_udp_router(self, name: str) -> Optional[Dict]:
        """Get a UDP router by name. Returns dict with service and entrypoints."""
        prefix = f"traefik/udp/routers/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        data = {'name': name, 'service': '', 'entrypoints': []}

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field == 'service':
                data['service'] = value
            elif field == 'entrypoints' or field.startswith('entrypoints/'):
                data['entrypoints'].append(value)

        return data

    def put_udp_router(self, name: str, service: str, entrypoints: List[str] = None) -> bool:
        """Write a UDP router to etcd."""
        prefix = f"traefik/udp/routers/{name}/"
        self.delete_prefix(prefix)
        success = True
        success &= self.put(f"{prefix}service", service)
        for i, ep in enumerate(entrypoints or []):
            success &= self.put(f"{prefix}entrypoints/{i}", ep)
        return success

    def delete_udp_router(self, name: str) -> bool:
        """Delete UDP router from etcd."""
        return self.delete_prefix(f"traefik/udp/routers/{name}/")

    # UDP Service Operations

    def list_udp_services(self) -> List[str]:
        """List all UDP service names."""
        kvs = self.get_prefix("traefik/udp/services/")
        services = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                services.add(parts[3])
        return sorted(list(services))

    def get_udp_service(self, name: str) -> Optional[UDPService]:
        """Get a UDP service by name."""
        prefix = f"traefik/udp/services/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        svc = UDPService(name=name, servers=[])

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field.startswith('loadBalancer/servers/'):
                parts = field.split('/')
                if len(parts) >= 4:
                    idx = int(parts[2])
                    while len(svc.servers) <= idx:
                        svc.servers.append(UDPServer(address=''))
                    if parts[3] == 'address':
                        svc.servers[idx].address = value

        return svc

    def put_udp_service(self, service: UDPService) -> bool:
        """Write a UDP service to etcd."""
        prefix = f"traefik/udp/services/{service.name}/"
        self.delete_prefix(prefix)
        success = True
        for i, server in enumerate(service.servers or []):
            success &= self.put(f"{prefix}loadBalancer/servers/{i}/address", server.address)
        return success

    def delete_udp_service(self, name: str) -> bool:
        """Delete UDP service from etcd."""
        return self.delete_prefix(f"traefik/udp/services/{name}/")

    # TLS Options Operations

    def list_tls_options(self) -> List[str]:
        """List all TLS option set names."""
        kvs = self.get_prefix("traefik/tls/options/")
        options = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                options.add(parts[3])
        return sorted(list(options))

    def get_tls_options(self, name: str) -> Optional[TLSOptions]:
        """Get TLS options by name."""
        prefix = f"traefik/tls/options/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        opts = TLSOptions(name=name)

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field == 'minVersion':
                opts.min_version = value
            elif field == 'maxVersion':
                opts.max_version = value
            elif field.startswith('cipherSuites/'):
                opts.cipher_suites.append(value)
            elif field.startswith('curvePreferences/'):
                opts.curve_preferences.append(value)
            elif field == 'sniStrict':
                opts.sni_strict = value.lower() == 'true'
            elif field == 'alpnProtocols':
                opts.alpn_protocols.append(value)
            elif field.startswith('alpnProtocols/'):
                opts.alpn_protocols.append(value)
            elif field == 'clientAuth/caFiles' or field.startswith('clientAuth/caFiles/'):
                opts.client_auth_ca_files.append(value)
            elif field == 'clientAuth/clientAuthType':
                opts.client_auth_type = value

        return opts

    def put_tls_options(self, options: TLSOptions) -> bool:
        """Write TLS options to etcd."""
        prefix = f"traefik/tls/options/{options.name}/"
        self.delete_prefix(prefix)
        success = True

        if options.min_version:
            success &= self.put(f"{prefix}minVersion", options.min_version)
        if options.max_version:
            success &= self.put(f"{prefix}maxVersion", options.max_version)
        for i, cs in enumerate(options.cipher_suites or []):
            success &= self.put(f"{prefix}cipherSuites/{i}", cs)
        for i, cp in enumerate(options.curve_preferences or []):
            success &= self.put(f"{prefix}curvePreferences/{i}", cp)
        if options.sni_strict:
            success &= self.put(f"{prefix}sniStrict", "true")
        for i, ap in enumerate(options.alpn_protocols or []):
            success &= self.put(f"{prefix}alpnProtocols/{i}", ap)
        for i, ca in enumerate(options.client_auth_ca_files or []):
            success &= self.put(f"{prefix}clientAuth/caFiles/{i}", ca)
        if options.client_auth_type:
            success &= self.put(f"{prefix}clientAuth/clientAuthType", options.client_auth_type)

        return success

    def delete_tls_options(self, name: str) -> bool:
        """Delete TLS options from etcd."""
        return self.delete_prefix(f"traefik/tls/options/{name}/")

    # TLS Store Operations

    def list_tls_stores(self) -> List[str]:
        """List all TLS store names."""
        kvs = self.get_prefix("traefik/tls/stores/")
        stores = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                stores.add(parts[3])
        return sorted(list(stores))

    def get_tls_store(self, name: str) -> Optional[TLSStore]:
        """Get TLS store by name."""
        prefix = f"traefik/tls/stores/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        store = TLSStore(name=name)

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field == 'defaultCertificate/certFile':
                store.default_certificate_cert = value
            elif field == 'defaultCertificate/keyFile':
                store.default_certificate_key = value
            elif field == 'defaultGeneratedCert/resolver':
                store.default_generated_cert_resolver = value
            elif field == 'defaultGeneratedCert/domain/main':
                store.default_generated_cert_domain_main = value
            elif field.startswith('defaultGeneratedCert/domain/sans/'):
                store.default_generated_cert_domain_sans.append(value)

        return store

    def put_tls_store(self, store: TLSStore) -> bool:
        """Write TLS store to etcd."""
        prefix = f"traefik/tls/stores/{store.name}/"
        self.delete_prefix(prefix)
        success = True

        if store.default_certificate_cert:
            success &= self.put(f"{prefix}defaultCertificate/certFile", store.default_certificate_cert)
        if store.default_certificate_key:
            success &= self.put(f"{prefix}defaultCertificate/keyFile", store.default_certificate_key)
        if store.default_generated_cert_resolver:
            success &= self.put(f"{prefix}defaultGeneratedCert/resolver", store.default_generated_cert_resolver)
        if store.default_generated_cert_domain_main:
            success &= self.put(f"{prefix}defaultGeneratedCert/domain/main", store.default_generated_cert_domain_main)
        for i, san in enumerate(store.default_generated_cert_domain_sans or []):
            success &= self.put(f"{prefix}defaultGeneratedCert/domain/sans/{i}", san)

        return success

    def delete_tls_store(self, name: str) -> bool:
        """Delete TLS store from etcd."""
        return self.delete_prefix(f"traefik/tls/stores/{name}/")

    # TLS Certificates Operations

    def list_tls_certificates(self) -> List[Dict[str, str]]:
        """List all TLS certificates."""
        kvs = self.get_prefix("traefik/tls/certificates/")
        certs = {}
        for key, value in kvs.items():
            parts = key.split('/')
            if len(parts) >= 5:
                idx = parts[3]
                field = parts[4]
                certs.setdefault(idx, {})[field] = value
        return list(certs.values())

    def put_tls_certificate(self, index: int, cert_file: str, key_file: str, stores: List[str] = None) -> bool:
        """Write a TLS certificate entry to etcd."""
        prefix = f"traefik/tls/certificates/{index}/"
        self.delete_prefix(prefix)
        success = True
        success &= self.put(f"{prefix}certFile", cert_file)
        success &= self.put(f"{prefix}keyFile", key_file)
        for i, store in enumerate(stores or []):
            success &= self.put(f"{prefix}stores/{i}", store)
        return success

    # HTTP ServersTransport Operations

    def list_servers_transports(self) -> List[str]:
        """List all HTTP serversTransport names."""
        kvs = self.get_prefix("traefik/http/serversTransports/")
        transports = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                transports.add(parts[3])
        return sorted(list(transports))

    def get_servers_transport(self, name: str) -> Optional[ServersTransport]:
        """Get HTTP serversTransport by name."""
        prefix = f"traefik/http/serversTransports/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        st = ServersTransport(name=name)

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field == 'serverName':
                st.server_name = value
            elif field == 'insecureSkipVerify':
                st.insecure_skip_verify = value.lower() == 'true'
            elif field.startswith('rootCAs/'):
                st.root_cas.append(value)
            elif field.startswith('certificates/'):
                parts = field.split('/')
                if len(parts) >= 3:
                    idx = int(parts[1])
                    while len(st.certificates) <= idx:
                        st.certificates.append({})
                    st.certificates[idx][parts[2]] = value
            elif field == 'maxIdleConnsPerHost':
                try: st.max_idle_conns_per_host = int(value)
                except ValueError: pass
            elif field == 'disableHTTP2':
                st.disable_http2 = value.lower() == 'true'
            elif field == 'peerCertURI':
                st.peer_cert_uri = value
            elif field.startswith('forwardingTimeouts/'):
                sf = field.replace('forwardingTimeouts/', '')
                st.forwarding_timeouts[sf] = value
            elif field.startswith('spiffe/'):
                sf = field.replace('spiffe/', '')
                st.spiffe[sf] = value

        return st

    def put_servers_transport(self, transport: ServersTransport) -> bool:
        """Write HTTP serversTransport to etcd."""
        prefix = f"traefik/http/serversTransports/{transport.name}/"
        self.delete_prefix(prefix)
        success = True

        if transport.server_name:
            success &= self.put(f"{prefix}serverName", transport.server_name)
        if transport.insecure_skip_verify:
            success &= self.put(f"{prefix}insecureSkipVerify", "true")
        for i, ca in enumerate(transport.root_cas or []):
            success &= self.put(f"{prefix}rootCAs/{i}", ca)
        for i, cert in enumerate(transport.certificates or []):
            for k, v in cert.items():
                success &= self.put(f"{prefix}certificates/{i}/{k}", v)
        if transport.max_idle_conns_per_host:
            success &= self.put(f"{prefix}maxIdleConnsPerHost", str(transport.max_idle_conns_per_host))
        if transport.disable_http2:
            success &= self.put(f"{prefix}disableHTTP2", "true")
        if transport.peer_cert_uri:
            success &= self.put(f"{prefix}peerCertURI", transport.peer_cert_uri)
        for k, v in (transport.forwarding_timeouts or {}).items():
            success &= self.put(f"{prefix}forwardingTimeouts/{k}", v)
        for k, v in (transport.spiffe or {}).items():
            success &= self.put(f"{prefix}spiffe/{k}", v)

        return success

    def delete_servers_transport(self, name: str) -> bool:
        """Delete HTTP serversTransport from etcd."""
        return self.delete_prefix(f"traefik/http/serversTransports/{name}/")

    # TCP ServersTransport Operations

    def list_tcp_servers_transports(self) -> List[str]:
        """List all TCP serversTransport names."""
        kvs = self.get_prefix("traefik/tcp/serversTransports/")
        transports = set()
        for key in kvs.keys():
            parts = key.split('/')
            if len(parts) >= 4:
                transports.add(parts[3])
        return sorted(list(transports))

    def get_tcp_servers_transport(self, name: str) -> Optional[TCPServersTransport]:
        """Get TCP serversTransport by name."""
        prefix = f"traefik/tcp/serversTransports/{name}/"
        kvs = self.get_prefix(prefix)
        if not kvs:
            return None

        st = TCPServersTransport(name=name)

        for key, value in kvs.items():
            field = key.replace(prefix, '')
            if field == 'tls/serverName':
                st.tls_server_name = value
            elif field == 'tls/insecureSkipVerify':
                st.tls_insecure_skip_verify = value.lower() == 'true'
            elif field.startswith('tls/rootCAs/'):
                st.tls_root_cas.append(value)
            elif field.startswith('tls/certificates/'):
                parts = field.split('/')
                if len(parts) >= 4:
                    idx = int(parts[2])
                    while len(st.tls_certificates) <= idx:
                        st.tls_certificates.append({})
                    st.tls_certificates[idx][parts[3]] = value
            elif field == 'tls/peerCertURI':
                st.tls_peer_cert_uri = value
            elif field == 'dialTimeout':
                st.dial_timeout = value
            elif field == 'dialKeepAlive':
                st.dial_keep_alive = value
            elif field.startswith('tls/spiffe/'):
                sf = field.replace('tls/spiffe/', '')
                st.tls_spiffe[sf] = value

        return st

    def put_tcp_servers_transport(self, transport: TCPServersTransport) -> bool:
        """Write TCP serversTransport to etcd."""
        prefix = f"traefik/tcp/serversTransports/{transport.name}/"
        self.delete_prefix(prefix)
        success = True

        if transport.tls_server_name:
            success &= self.put(f"{prefix}tls/serverName", transport.tls_server_name)
        if transport.tls_insecure_skip_verify:
            success &= self.put(f"{prefix}tls/insecureSkipVerify", "true")
        for i, ca in enumerate(transport.tls_root_cas or []):
            success &= self.put(f"{prefix}tls/rootCAs/{i}", ca)
        for i, cert in enumerate(transport.tls_certificates or []):
            for k, v in cert.items():
                success &= self.put(f"{prefix}tls/certificates/{i}/{k}", v)
        if transport.tls_peer_cert_uri:
            success &= self.put(f"{prefix}tls/peerCertURI", transport.tls_peer_cert_uri)
        if transport.dial_timeout:
            success &= self.put(f"{prefix}dialTimeout", transport.dial_timeout)
        if transport.dial_keep_alive:
            success &= self.put(f"{prefix}dialKeepAlive", transport.dial_keep_alive)
        for k, v in (transport.tls_spiffe or {}).items():
            success &= self.put(f"{prefix}tls/spiffe/{k}", v)

        return success

    def delete_tcp_servers_transport(self, name: str) -> bool:
        """Delete TCP serversTransport from etcd."""
        return self.delete_prefix(f"traefik/tcp/serversTransports/{name}/")
    
    # Utility Methods
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '/') -> Dict[str, Any]:
        """
        Flatten nested dictionary to etcd key-value pairs.
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key prefix
            sep: Key separator
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        items.extend(self._flatten_dict(item, f"{new_key}/{i}", sep=sep).items())
                    else:
                        items.append((f"{new_key}/{i}", item))
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    def health_check(self) -> bool:
        """
        Check if etcd is reachable.
        
        Returns:
            True if etcd is healthy
        """
        try:
            response = requests.get(
                f"{self.etcd_url}/health",
                timeout=self.timeout
            )
            return response.status_code == 200
        except:
            return False
    
    def get_all_traefik_config(self) -> Dict[str, str]:
        """
        Get all Traefik configuration from etcd.
        
        Returns:
            Dict of all keys under traefik/
        """
        return self.get_prefix("traefik/")
    
    def export_config(self) -> Dict[str, Any]:
        """
        Export all Traefik configuration as structured data.
        
        Returns:
            Structured configuration dict
        """
        config = {
            'http': {
                'routers': [],
                'services': [],
                'middlewares': [],
                'serversTransports': [],
            },
            'tcp': {
                'routers': [],
                'services': [],
                'middlewares': [],
                'serversTransports': [],
            },
            'udp': {
                'routers': [],
                'services': [],
            },
            'tls': {
                'options': [],
                'stores': [],
                'certificates': [],
            },
        }
        
        # HTTP routers
        for router in self.list_http_routers():
            tls_payload = None
            if router.tls:
                cert_resolver = self._extract_tls_cert_resolver(router.tls)
                options = self._extract_tls_options(router.tls)
                domains = self._extract_tls_domains(router.tls)
                tls_payload = {
                    'cert_resolver': cert_resolver,
                    'options': options,
                    'domains': domains,
                }
            obs_payload = None
            if router.observability:
                obs_payload = {
                    'access_logs': router.observability.access_logs,
                    'metrics': router.observability.metrics,
                    'tracing': router.observability.tracing,
                }

            config['http']['routers'].append({
                'name': router.name,
                'rule': router.rule,
                'service': router.service,
                'entrypoints': list(router.entrypoints or []),
                'middlewares': list(router.middlewares or []),
                'priority': int(router.priority or 0),
                'tls': tls_payload,
                'observability': obs_payload,
            })
        
        # HTTP services / middlewares
        config['http']['services'] = self.list_http_services()
        config['http']['middlewares'] = self.list_http_middlewares()
        config['http']['serversTransports'] = self.list_servers_transports()

        # TCP
        config['tcp']['routers'] = self.list_tcp_routers()
        config['tcp']['services'] = self.list_tcp_services()
        config['tcp']['middlewares'] = self.list_tcp_middlewares()
        config['tcp']['serversTransports'] = self.list_tcp_servers_transports()

        # UDP
        config['udp']['routers'] = self.list_udp_routers()
        config['udp']['services'] = self.list_udp_services()

        # TLS
        config['tls']['options'] = self.list_tls_options()
        config['tls']['stores'] = self.list_tls_stores()
        config['tls']['certificates'] = self.list_tls_certificates()
        
        return config
