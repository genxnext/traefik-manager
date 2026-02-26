"""
ConfigManager - Manages configuration validation, caching, and domain registry.

This module provides high-level configuration management including:
- Domain registry and default domain management
- Configuration validation
- Caching layer for performance
- Default middleware and entrypoint management
"""

import json
import re
from typing import List, Dict, Optional, Set, Any
from dataclasses import asdict, replace
from collections import defaultdict

from .models import (
    Router, TCPRouter, UDPRouter, Service, Domain, GlobalConfig,
    MiddlewareType, TCPMiddlewareType, Protocol, TLSConfig, Observability,
    TCPServer, TCPService, UDPServer, UDPService,
    TLSOptions, TLSStore,
    ServersTransport, TCPServersTransport,
)
from .etcd_client import ETCDClient


class ValidationError(Exception):
    """Configuration validation error."""
    pass


class ConfigManager:
    """
    High-level configuration manager with validation and caching.
    """

    VALID_HTTP_ENTRYPOINTS = {'web', 'websecure'}
    VALID_TCP_ENTRYPOINTS = {'tcp', 'tcp-secure'}
    VALID_UDP_ENTRYPOINTS = {'udp'}
    
    def __init__(self, etcd_client: ETCDClient):
        """
        Initialize config manager.
        
        Args:
            etcd_client: ETCDClient instance
        """
        self.etcd = etcd_client
        self._router_cache: Dict[str, Router] = {}
        self._service_cache: Set[str] = set()
        self._middleware_cache: Set[str] = set()
        self._tcp_router_cache: Set[str] = set()
        self._tcp_service_cache: Set[str] = set()
        self._tcp_middleware_cache: Set[str] = set()
        self._udp_router_cache: Set[str] = set()
        self._udp_service_cache: Set[str] = set()
        self._tls_options_cache: Set[str] = set()
        self._tls_store_cache: Set[str] = set()
        self._servers_transport_cache: Set[str] = set()
        self._tcp_servers_transport_cache: Set[str] = set()
        self._domain_registry: List[Domain] = []
        self._global_config: Optional[GlobalConfig] = None
        self._cache_valid = False
        
        # Load global config
        self._load_global_config()
    
    def _load_global_config(self):
        """Load global configuration from etcd."""
        config_key = "traefik/config/global"
        config_data = self.etcd.get(config_key)
        
        if config_data:
            try:
                data = json.loads(config_data)
                # Convert domain dicts to Domain objects
                if 'domains' in data and isinstance(data['domains'], list):
                    data['domains'] = [
                        Domain(**d) if isinstance(d, dict) else d
                        for d in data['domains']
                    ]
                self._global_config = GlobalConfig(**data)
            except:
                self._global_config = self._create_default_global_config()
        else:
            self._global_config = self._create_default_global_config()
            self._save_global_config()
    
    def _save_global_config(self):
        """Save global configuration to etcd."""
        if self._global_config:
            config_key = "traefik/config/global"
            config_data = json.dumps(asdict(self._global_config))
            self.etcd.put(config_key, config_data)
    
    def _create_default_global_config(self) -> GlobalConfig:
        """Create default global configuration."""
        return GlobalConfig(
            domains=[Domain(name="monoztap.com", cert_resolver="letsencrypt", is_default=True, sans=[])],
            default_cert_resolver="letsencrypt",
            default_entrypoint="websecure",
            default_middlewares=[],
            default_health_endpoint="/health",
            default_health_interval="10s",
            default_health_timeout="3s"
        )
    
    def invalidate_cache(self):
        """Invalidate all caches."""
        self._cache_valid = False
        self._router_cache.clear()
        self._service_cache.clear()
        self._middleware_cache.clear()
        self._tcp_router_cache.clear()
        self._tcp_service_cache.clear()
        self._tcp_middleware_cache.clear()
        self._udp_router_cache.clear()
        self._udp_service_cache.clear()
        self._tls_options_cache.clear()
        self._tls_store_cache.clear()
        self._servers_transport_cache.clear()
        self._tcp_servers_transport_cache.clear()
    
    def refresh_cache(self):
        """Refresh all caches from etcd."""
        self.invalidate_cache()
        
        # Load HTTP entities
        routers = self.etcd.list_http_routers()
        self._router_cache = {r.name: r for r in routers}
        self._service_cache = set(self.etcd.list_http_services())
        self._middleware_cache = set(self.etcd.list_http_middlewares())
        self._servers_transport_cache = set(self.etcd.list_servers_transports())
        
        # Load TCP entities
        self._tcp_router_cache = set(self.etcd.list_tcp_routers())
        self._tcp_service_cache = set(self.etcd.list_tcp_services())
        self._tcp_middleware_cache = set(self.etcd.list_tcp_middlewares())
        self._tcp_servers_transport_cache = set(self.etcd.list_tcp_servers_transports())
        
        # Load UDP entities
        self._udp_router_cache = set(self.etcd.list_udp_routers())
        self._udp_service_cache = set(self.etcd.list_udp_services())
        
        # Load TLS entities
        self._tls_options_cache = set(self.etcd.list_tls_options())
        self._tls_store_cache = set(self.etcd.list_tls_stores())
        
        self._cache_valid = True
    
    def _ensure_cache(self):
        """Ensure cache is loaded."""
        if not self._cache_valid:
            self.refresh_cache()
    
    # Domain Management
    
    def get_domains(self) -> List[Domain]:
        """Get all registered domains."""
        if self._global_config:
            return self._global_config.domains.copy()
        return []
    
    def get_default_domain(self) -> Optional[Domain]:
        """Get the default domain."""
        for domain in self.get_domains():
            if domain.is_default:
                return domain
        # Return first domain if none marked as default
        domains = self.get_domains()
        return domains[0] if domains else None
    
    def add_domain(self, domain: Domain, set_as_default: bool = False) -> bool:
        """
        Add a domain to the registry.
        
        Args:
            domain: Domain to add
            set_as_default: Set this as the default domain
            
        Returns:
            True on success
        """
        if not self._global_config:
            return False
        
        # Check if domain already exists
        existing = [d for d in self._global_config.domains if d.name == domain.name]
        if existing:
            return False
        
        # If setting as default, unmark others
        if set_as_default:
            for d in self._global_config.domains:
                d.is_default = False
            domain.is_default = True
        
        self._global_config.domains.append(domain)
        self._save_global_config()
        return True
    
    def remove_domain(self, domain_name: str) -> bool:
        """
        Remove a domain from the registry.
        
        Args:
            domain_name: Name of domain to remove
            
        Returns:
            True on success
        """
        if not self._global_config:
            return False
        
        # Don't allow removing last domain
        if len(self._global_config.domains) <= 1:
            return False
        
        # Find and remove domain
        was_default = False
        self._global_config.domains = [
            d for d in self._global_config.domains
            if d.name != domain_name or (was_default := d.is_default, False)[1]
        ]
        
        # If removed domain was default, set first domain as default
        if was_default and self._global_config.domains:
            self._global_config.domains[0].is_default = True
        
        self._save_global_config()
        return True
    
    def set_default_domain(self, domain_name: str) -> bool:
        """
        Set a domain as the default.
        
        Args:
            domain_name: Domain name to set as default
            
        Returns:
            True on success
        """
        if not self._global_config:
            return False
        
        found = False
        for domain in self._global_config.domains:
            if domain.name == domain_name:
                domain.is_default = True
                found = True
            else:
                domain.is_default = False
        
        if found:
            self._save_global_config()
        
        return found
    
    def update_domain(self, domain_name: str, cert_resolver: Optional[str] = None, 
                     sans: Optional[List[str]] = None) -> bool:
        """
        Update domain configuration.
        
        Args:
            domain_name: Domain name to update
            cert_resolver: New certificate resolver (if provided)
            sans: New SANs list (if provided)
            
        Returns:
            True on success
        """
        if not self._global_config:
            return False
        
        # Find domain
        domain = next((d for d in self._global_config.domains if d.name == domain_name), None)
        if not domain:
            return False
        
        # Update fields
        if cert_resolver is not None:
            domain.cert_resolver = cert_resolver
        if sans is not None:
            domain.sans = sans
        
        self._save_global_config()
        return True
    
    # Router Management with Validation
    
    def validate_router(self, router: Router) -> List[str]:
        """
        Validate router configuration.
        
        Args:
            router: Router to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Name validation
        if not router.name:
            errors.append("Router name is required")
        elif not re.match(r'^[a-zA-Z0-9-_]+$', router.name):
            errors.append("Router name must contain only alphanumeric characters, hyphens, and underscores")
        
        # Rule validation
        if not router.rule:
            errors.append("Router rule is required")
        else:
            # Basic rule syntax validation
            if not any([
                'Host(' in router.rule,
                'PathPrefix(' in router.rule,
                'Path(' in router.rule,
                'Headers(' in router.rule,
                'Method(' in router.rule,
                'Query(' in router.rule,
                'ClientIP(' in router.rule
            ]):
                errors.append("Router rule must contain at least one matcher (Host, PathPrefix, etc.)")
        
        # Service validation
        if not router.service:
            errors.append("Router service is required")
        
        # Entrypoints validation
        if not router.entrypoints:
            errors.append("Router must have at least one entrypoint")
        else:
            for ep in router.entrypoints:
                if ep not in self.VALID_HTTP_ENTRYPOINTS:
                    errors.append(f"Invalid HTTP entrypoint: {ep}")
        
        # Middlewares validation (check they exist)
        self._ensure_cache()
        for mw in router.middlewares:
            if mw not in self._middleware_cache:
                errors.append(f"Middleware not found: {mw}")
        
        # TLS validation
        if router.tls:
            if router.tls.cert_resolver and not re.match(r'^[a-zA-Z0-9-_]+$', router.tls.cert_resolver):
                errors.append("Invalid cert resolver name")
        
        # Priority validation
        if router.priority < 0:
            errors.append("Priority must be non-negative")
        
        return errors

    def validate_tcp_router(self, router: TCPRouter) -> List[str]:
        """Validate TCP router configuration against allowed fixed selectors."""
        errors = []

        if not router.name or not re.match(r'^[a-zA-Z0-9-_]+$', router.name):
            errors.append("TCP router name must contain only alphanumeric characters, hyphens, and underscores")

        if not router.rule:
            errors.append("TCP router rule is required")

        if not router.service:
            errors.append("TCP router service is required")

        if not router.entrypoints:
            errors.append("TCP router must have at least one entrypoint")
        else:
            for ep in router.entrypoints:
                if ep not in self.VALID_TCP_ENTRYPOINTS:
                    errors.append(f"Invalid TCP entrypoint: {ep}")

        self._ensure_cache()
        if router.service not in self._tcp_service_cache:
            errors.append(f"TCP service not found: {router.service}")

        for mw in router.middlewares:
            if mw not in self._tcp_middleware_cache:
                errors.append(f"TCP middleware not found: {mw}")

        if router.priority < 0:
            errors.append("TCP router priority must be non-negative")

        if router.tls and router.tls.cert_resolver and not re.match(r'^[a-zA-Z0-9-_]+$', router.tls.cert_resolver):
            errors.append("Invalid TCP cert resolver name")

        return errors

    def validate_udp_router(self, name: str, service: str, entrypoints: List[str]) -> List[str]:
        """Validate UDP router configuration against allowed fixed selectors."""
        errors = []

        if not name or not re.match(r'^[a-zA-Z0-9-_]+$', name):
            errors.append("UDP router name must contain only alphanumeric characters, hyphens, and underscores")

        if not service:
            errors.append("UDP router service is required")

        if not entrypoints:
            errors.append("UDP router must have at least one entrypoint")
        else:
            for ep in entrypoints:
                if ep not in self.VALID_UDP_ENTRYPOINTS:
                    errors.append(f"Invalid UDP entrypoint: {ep}")

        self._ensure_cache()
        if service and service not in self._udp_service_cache:
            errors.append(f"UDP service not found: {service}")

        return errors
    
    def create_router(self, router: Router, validate: bool = True) -> bool:
        """
        Create a new router with validation.
        
        Args:
            router: Router to create
            validate: Whether to validate before creating
            
        Returns:
            True on success
            
        Raises:
            ValidationError: If validation fails
        """
        if validate:
            errors = self.validate_router(router)
            if errors:
                raise ValidationError("\n".join(errors))
        
        # Check if router already exists
        self._ensure_cache()
        if router.name in self._router_cache:
            raise ValidationError(f"Router '{router.name}' already exists")
        
        # Create router in etcd
        success = self.etcd.put_http_router(router)
        
        if success:
            self._router_cache[router.name] = router
        
        return success
    
    def update_router(self, router: Router, validate: bool = True) -> bool:
        """
        Update an existing router with validation.
        
        Args:
            router: Router to update
            validate: Whether to validate before updating
            
        Returns:
            True on success
            
        Raises:
            ValidationError: If validation fails
        """
        if validate:
            errors = self.validate_router(router)
            if errors:
                raise ValidationError("\n".join(errors))
        
        # Check if router exists
        self._ensure_cache()
        if router.name not in self._router_cache:
            raise ValidationError(f"Router '{router.name}' does not exist")
        
        # Update router in etcd
        success = self.etcd.put_http_router(router)
        
        if success:
            self._router_cache[router.name] = router
        
        return success
    
    def delete_router(self, name: str) -> bool:
        """
        Delete a router.
        
        Args:
            name: Router name
            
        Returns:
            True on success
        """
        success = self.etcd.delete_http_router(name)
        
        if success:
            self._router_cache.pop(name, None)
        
        return success
    
    def get_router(self, name: str) -> Optional[Router]:
        """
        Get a router by name.
        
        Args:
            name: Router name
            
        Returns:
            Router if found, None otherwise
        """
        self._ensure_cache()
        return self._router_cache.get(name)
    
    def list_routers(self) -> List[Router]:
        """
        List all routers.
        
        Returns:
            List of routers
        """
        self._ensure_cache()
        return list(self._router_cache.values())
    
    # Service Management
    
    def list_services(self) -> List[str]:
        """
        List all service names.
        
        Returns:
            List of service names
        """
        self._ensure_cache()
        return sorted(list(self._service_cache))
    
    def service_exists(self, name: str) -> bool:
        """
        Check if a service exists.
        
        Args:
            name: Service name
            
        Returns:
            True if service exists
        """
        self._ensure_cache()
        return name in self._service_cache
    
    def create_simple_service(self, name: str, url: str) -> bool:
        """
        Create a simple service with one server.
        
        Args:
            name: Service name
            url: Server URL
            
        Returns:
            True on success
        """
        success = self.etcd.put_http_service_simple(name, url)
        
        if success:
            self._service_cache.add(name)
        
        return success

    def delete_service(self, name: str) -> bool:
        """
        Delete a service.

        Args:
            name: Service name

        Returns:
            True on success
        """
        success = self.etcd.delete_http_service(name)

        if success:
            self._service_cache.discard(name)

        return success
    
    # Middleware Management
    
    def list_middlewares(self) -> List[str]:
        """
        List all middleware names.
        
        Returns:
            List of middleware names
        """
        self._ensure_cache()
        return sorted(list(self._middleware_cache))
    
    def middleware_exists(self, name: str) -> bool:
        """
        Check if a middleware exists.
        
        Args:
            name: Middleware name
            
        Returns:
            True if middleware exists
        """
        self._ensure_cache()
        return name in self._middleware_cache
    
    def create_middleware(self, name: str, middleware_type: MiddlewareType, config: Any) -> bool:
        """
        Create a middleware.
        
        Args:
            name: Middleware name
            middleware_type: Middleware type
            config: Middleware configuration object
            
        Returns:
            True on success
        """
        success = self.etcd.put_http_middleware(name, middleware_type, config)
        
        if success:
            self._middleware_cache.add(name)
        
        return success
    
    def delete_middleware(self, name: str) -> bool:
        """
        Delete a middleware.
        
        Args:
            name: Middleware name
            
        Returns:
            True on success
        """
        # Check if middleware is in use
        self._ensure_cache()
        routers_using = [
            r.name for r in self._router_cache.values()
            if name in r.middlewares
        ]
        
        if routers_using:
            raise ValidationError(
                f"Cannot delete middleware '{name}': "
                f"used by routers: {', '.join(routers_using)}"
            )
        
        success = self.etcd.delete_http_middleware(name)
        
        if success:
            self._middleware_cache.discard(name)
        
        return success
    
    # Smart Defaults and Learning

    # ============================================================
    # Full Service Management (with Service model)
    # ============================================================

    def get_service(self, name: str) -> Optional[Service]:
        """Get a full HTTP service object by name."""
        return self.etcd.get_http_service(name)

    def create_service(self, service: Service) -> bool:
        """Create an HTTP service using the full Service model."""
        success = self.etcd.put_http_service(service)
        if success:
            self._service_cache.add(service.name)
        return success

    def update_service(self, service: Service) -> bool:
        """Update an HTTP service using the full Service model."""
        success = self.etcd.put_http_service(service)
        if success:
            self._service_cache.add(service.name)
        return success

    # ============================================================
    # TCP Router Management
    # ============================================================

    def list_tcp_routers(self) -> List[str]:
        """List all TCP router names."""
        self._ensure_cache()
        return sorted(list(self._tcp_router_cache))

    def get_tcp_router(self, name: str) -> Optional[TCPRouter]:
        """Get a TCP router by name."""
        return self.etcd.get_tcp_router(name)

    def create_tcp_router(self, router: TCPRouter) -> bool:
        """Create a TCP router."""
        errors = self.validate_tcp_router(router)
        if errors:
            raise ValidationError("\n".join(errors))
        success = self.etcd.put_tcp_router(router)
        if success:
            self._tcp_router_cache.add(router.name)
        return success

    def update_tcp_router(self, router: TCPRouter) -> bool:
        """Update a TCP router."""
        errors = self.validate_tcp_router(router)
        if errors:
            raise ValidationError("\n".join(errors))
        success = self.etcd.put_tcp_router(router)
        if success:
            self._tcp_router_cache.add(router.name)
        return success

    def delete_tcp_router(self, name: str) -> bool:
        """Delete a TCP router."""
        success = self.etcd.delete_tcp_router(name)
        if success:
            self._tcp_router_cache.discard(name)
        return success

    # ============================================================
    # TCP Service Management
    # ============================================================

    def list_tcp_services(self) -> List[str]:
        """List all TCP service names."""
        self._ensure_cache()
        return sorted(list(self._tcp_service_cache))

    def get_tcp_service(self, name: str) -> Optional[TCPService]:
        """Get a TCP service by name."""
        return self.etcd.get_tcp_service(name)

    def create_tcp_service(self, service: TCPService) -> bool:
        """Create a TCP service."""
        success = self.etcd.put_tcp_service(service)
        if success:
            self._tcp_service_cache.add(service.name)
        return success

    def update_tcp_service(self, service: TCPService) -> bool:
        """Update a TCP service."""
        success = self.etcd.put_tcp_service(service)
        if success:
            self._tcp_service_cache.add(service.name)
        return success

    def delete_tcp_service(self, name: str) -> bool:
        """Delete a TCP service."""
        success = self.etcd.delete_tcp_service(name)
        if success:
            self._tcp_service_cache.discard(name)
        return success

    # ============================================================
    # TCP Middleware Management
    # ============================================================

    def list_tcp_middlewares(self) -> List[str]:
        """List all TCP middleware names."""
        self._ensure_cache()
        return sorted(list(self._tcp_middleware_cache))

    def get_tcp_middleware(self, name: str):
        """Get a TCP middleware. Returns (TCPMiddlewareType, config) or None."""
        return self.etcd.get_tcp_middleware(name)

    def create_tcp_middleware(self, name: str, mw_type: TCPMiddlewareType, config: Dict) -> bool:
        """Create a TCP middleware."""
        success = self.etcd.put_tcp_middleware(name, mw_type, config)
        if success:
            self._tcp_middleware_cache.add(name)
        return success

    def delete_tcp_middleware(self, name: str) -> bool:
        """Delete a TCP middleware."""
        success = self.etcd.delete_tcp_middleware(name)
        if success:
            self._tcp_middleware_cache.discard(name)
        return success

    # ============================================================
    # UDP Router Management
    # ============================================================

    def list_udp_routers(self) -> List[str]:
        """List all UDP router names."""
        self._ensure_cache()
        return sorted(list(self._udp_router_cache))

    def get_udp_router(self, name: str) -> Optional[Dict]:
        """Get a UDP router by name."""
        return self.etcd.get_udp_router(name)

    def create_udp_router(self, name: str, service: str, entrypoints: List[str] = None) -> bool:
        """Create a UDP router."""
        entrypoints = entrypoints or ['udp']
        errors = self.validate_udp_router(name, service, entrypoints)
        if errors:
            raise ValidationError("\n".join(errors))
        success = self.etcd.put_udp_router(name, service, entrypoints)
        if success:
            self._udp_router_cache.add(name)
        return success

    def delete_udp_router(self, name: str) -> bool:
        """Delete a UDP router."""
        success = self.etcd.delete_udp_router(name)
        if success:
            self._udp_router_cache.discard(name)
        return success

    # ============================================================
    # UDP Service Management
    # ============================================================

    def list_udp_services(self) -> List[str]:
        """List all UDP service names."""
        self._ensure_cache()
        return sorted(list(self._udp_service_cache))

    def get_udp_service(self, name: str) -> Optional[UDPService]:
        """Get a UDP service by name."""
        return self.etcd.get_udp_service(name)

    def create_udp_service(self, service: UDPService) -> bool:
        """Create a UDP service."""
        success = self.etcd.put_udp_service(service)
        if success:
            self._udp_service_cache.add(service.name)
        return success

    def delete_udp_service(self, name: str) -> bool:
        """Delete a UDP service."""
        success = self.etcd.delete_udp_service(name)
        if success:
            self._udp_service_cache.discard(name)
        return success

    # ============================================================
    # TLS Options Management
    # ============================================================

    def list_tls_options(self) -> List[str]:
        """List all TLS option names."""
        self._ensure_cache()
        return sorted(list(self._tls_options_cache))

    def get_tls_options(self, name: str) -> Optional[TLSOptions]:
        """Get TLS options by name."""
        return self.etcd.get_tls_options(name)

    def create_tls_options(self, options: TLSOptions) -> bool:
        """Create TLS options."""
        success = self.etcd.put_tls_options(options)
        if success:
            self._tls_options_cache.add(options.name)
        return success

    def update_tls_options(self, options: TLSOptions) -> bool:
        """Update TLS options."""
        return self.create_tls_options(options)

    def delete_tls_options(self, name: str) -> bool:
        """Delete TLS options."""
        success = self.etcd.delete_tls_options(name)
        if success:
            self._tls_options_cache.discard(name)
        return success

    # ============================================================
    # TLS Store Management
    # ============================================================

    def list_tls_stores(self) -> List[str]:
        """List all TLS store names."""
        self._ensure_cache()
        return sorted(list(self._tls_store_cache))

    def get_tls_store(self, name: str) -> Optional[TLSStore]:
        """Get TLS store by name."""
        return self.etcd.get_tls_store(name)

    def create_tls_store(self, store: TLSStore) -> bool:
        """Create TLS store."""
        success = self.etcd.put_tls_store(store)
        if success:
            self._tls_store_cache.add(store.name)
        return success

    def update_tls_store(self, store: TLSStore) -> bool:
        """Update TLS store."""
        return self.create_tls_store(store)

    def delete_tls_store(self, name: str) -> bool:
        """Delete TLS store."""
        success = self.etcd.delete_tls_store(name)
        if success:
            self._tls_store_cache.discard(name)
        return success

    # ============================================================
    # TLS Certificate Management
    # ============================================================

    def list_tls_certificates(self) -> List[Dict[str, str]]:
        """List all TLS certificates."""
        return self.etcd.list_tls_certificates()

    def add_tls_certificate(self, index: int, cert_file: str, key_file: str, stores: List[str] = None) -> bool:
        """Add a TLS certificate entry."""
        return self.etcd.put_tls_certificate(index, cert_file, key_file, stores)

    # ============================================================
    # HTTP ServersTransport Management
    # ============================================================

    def list_servers_transports(self) -> List[str]:
        """List all HTTP serversTransport names."""
        self._ensure_cache()
        return sorted(list(self._servers_transport_cache))

    def get_servers_transport(self, name: str) -> Optional[ServersTransport]:
        """Get HTTP serversTransport by name."""
        return self.etcd.get_servers_transport(name)

    def create_servers_transport(self, transport: ServersTransport) -> bool:
        """Create HTTP serversTransport."""
        success = self.etcd.put_servers_transport(transport)
        if success:
            self._servers_transport_cache.add(transport.name)
        return success

    def update_servers_transport(self, transport: ServersTransport) -> bool:
        """Update HTTP serversTransport."""
        return self.create_servers_transport(transport)

    def delete_servers_transport(self, name: str) -> bool:
        """Delete HTTP serversTransport."""
        success = self.etcd.delete_servers_transport(name)
        if success:
            self._servers_transport_cache.discard(name)
        return success

    # ============================================================
    # TCP ServersTransport Management
    # ============================================================

    def list_tcp_servers_transports(self) -> List[str]:
        """List all TCP serversTransport names."""
        self._ensure_cache()
        return sorted(list(self._tcp_servers_transport_cache))

    def get_tcp_servers_transport(self, name: str) -> Optional[TCPServersTransport]:
        """Get TCP serversTransport by name."""
        return self.etcd.get_tcp_servers_transport(name)

    def create_tcp_servers_transport(self, transport: TCPServersTransport) -> bool:
        """Create TCP serversTransport."""
        success = self.etcd.put_tcp_servers_transport(transport)
        if success:
            self._tcp_servers_transport_cache.add(transport.name)
        return success

    def update_tcp_servers_transport(self, transport: TCPServersTransport) -> bool:
        """Update TCP serversTransport."""
        return self.create_tcp_servers_transport(transport)

    def delete_tcp_servers_transport(self, name: str) -> bool:
        """Delete TCP serversTransport."""
        success = self.etcd.delete_tcp_servers_transport(name)
        if success:
            self._tcp_servers_transport_cache.discard(name)
        return success
    
    # Smart Defaults and Learning (original section below)
    
    def suggest_service_name(self, router_name: str) -> str:
        """
        Suggest a service name based on router name.
        
        Args:
            router_name: Router name
            
        Returns:
            Suggested service name
        """
        base_name = f"{router_name}-svc"
        
        # If service doesn't exist, use it
        if not self.service_exists(base_name):
            return base_name
        
        # Otherwise, append number
        i = 2
        while self.service_exists(f"{base_name}-{i}"):
            i += 1
        
        return f"{base_name}-{i}"
    
    def suggest_middlewares(self, router: Router) -> List[str]:
        """
        Suggest middlewares based on router configuration.
        
        Args:
            router: Router
            
        Returns:
            List of suggested middleware names
        """
        suggestions = []
        
        # If HTTPS, suggest security headers
        if router.tls:
            for mw in self.list_middlewares():
                if 'secure' in mw.lower() or 'header' in mw.lower():
                    if mw not in suggestions:
                        suggestions.append(mw)
        
        # If API route, suggest rate limiting
        if 'api' in router.name.lower() or '/api' in router.rule.lower():
            for mw in self.list_middlewares():
                if 'rate' in mw.lower() or 'limit' in mw.lower():
                    if mw not in suggestions:
                        suggestions.append(mw)
        
        return suggestions[:5]  # Limit to 5 suggestions
    
    def learn_from_routers(self) -> Dict[str, Any]:
        """
        Analyze existing routers to learn common patterns.
        
        Returns:
            Dict of learned patterns
        """
        self._ensure_cache()
        
        if not self._router_cache:
            return {}
        
        # Analyze patterns
        entrypoint_usage = defaultdict(int)
        middleware_usage = defaultdict(int)
        service_patterns = defaultdict(int)
        tls_usage = {'enabled': 0, 'disabled': 0}
        
        for router in self._router_cache.values():
            for ep in router.entrypoints:
                entrypoint_usage[ep] += 1
            
            for mw in router.middlewares:
                middleware_usage[mw] += 1
            
            if router.tls:
                tls_usage['enabled'] += 1
            else:
                tls_usage['disabled'] += 1
            
            # Analyze service naming patterns
            service_suffix = router.service.split('-')[-1] if '-' in router.service else ''
            if service_suffix:
                service_patterns[service_suffix] += 1
        
        return {
            'common_entrypoints': sorted(entrypoint_usage.items(), key=lambda x: x[1], reverse=True),
            'common_middlewares': sorted(middleware_usage.items(), key=lambda x: x[1], reverse=True),
            'common_service_suffixes': sorted(service_patterns.items(), key=lambda x: x[1], reverse=True),
            'tls_preference': 'enabled' if tls_usage['enabled'] > tls_usage['disabled'] else 'disabled',
            'total_routers': len(self._router_cache)
        }
    
    # Export/Import
    
    def export_full_config(self) -> Dict[str, Any]:
        """
        Export complete configuration including global settings.
        
        Returns:
            Full configuration dict
        """
        config = self.etcd.export_config()
        config['global'] = asdict(self._global_config) if self._global_config else {}
        config['metadata'] = {
            'learned_patterns': self.learn_from_routers()
        }
        return config
    
    def import_routers(self, routers_data: List[Dict], merge: bool = True) -> tuple[int, int]:
        """
        Import routers from configuration data.
        
        Args:
            routers_data: List of router dicts
            merge: If True, merge with existing; if False, replace
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        if not merge:
            # Delete all existing routers
            for name in list(self._router_cache.keys()):
                self.delete_router(name)
        
        success = 0
        failure = 0
        
        for router_dict in routers_data:
            try:
                router_payload = dict(router_dict)
                tls_payload = router_payload.get('tls')
                if isinstance(tls_payload, dict):
                    router_payload['tls'] = TLSConfig(
                        cert_resolver=tls_payload.get('cert_resolver') or tls_payload.get('certresolver', ''),
                        options=tls_payload.get('options', ''),
                        domains=tls_payload.get('domains', []) if isinstance(tls_payload.get('domains', []), list) else [],
                    )

                router = Router(**router_payload)
                if merge and router.name in self._router_cache:
                    self.update_router(router, validate=True)
                else:
                    self.create_router(router, validate=True)
                success += 1
            except Exception:
                failure += 1
        
        return (success, failure)
