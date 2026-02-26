"""
Core module for Traefik configuration management.

This module contains data models, etcd client, and configuration management logic.
"""

from .models import (
    # Enums
    Protocol,
    MiddlewareType,
    TCPMiddlewareType,
    LoadBalancerMethod,
    HealthStatus,
    ServiceType,
    
    # Middleware Models
    AddPrefixMiddleware,
    StripPrefixMiddleware,
    HeadersMiddleware,
    RateLimitMiddleware,
    CircuitBreakerMiddleware,
    RetryMiddleware,
    CompressMiddleware,
    BasicAuthMiddleware,
    DigestAuthMiddleware,
    ForwardAuthMiddleware,
    IPWhiteListMiddleware,
    RedirectSchemeMiddleware,
    RedirectRegexMiddleware,
    BufferingMiddleware,
    InFlightReqMiddleware,
    
    # Service Models
    HealthCheck,
    StickyCookie,
    Server,
    LoadBalancerService,
    WeightedService,
    MirrorService,
    FailoverService,
    Service,
    
    # TCP/UDP Models
    TCPServer,
    TCPService,
    UDPServer,
    UDPService,
    
    # TLS Models
    TLSOptions,
    TLSStore,
    
    # ServersTransport Models
    ServersTransport,
    TCPServersTransport,
    
    # Router Models
    TLSConfig,
    Observability,
    Router,
    TCPRouter,
    UDPRouter,
    
    # Configuration Models
    Domain,
    GlobalConfig,
    
    # Helper Functions
    middleware_from_dict,
    middleware_to_dict,
)

from .etcd_client import ETCDClient, ETCDException
from .config_manager import ConfigManager, ValidationError

__all__ = [
    # Enums
    'Protocol',
    'MiddlewareType',
    'TCPMiddlewareType',
    'LoadBalancerMethod',
    'HealthStatus',
    'ServiceType',
    
    # Middleware Models
    'AddPrefixMiddleware',
    'StripPrefixMiddleware',
    'HeadersMiddleware',
    'RateLimitMiddleware',
    'CircuitBreakerMiddleware',
    'RetryMiddleware',
    'CompressMiddleware',
    'BasicAuthMiddleware',
    'DigestAuthMiddleware',
    'ForwardAuthMiddleware',
    'IPWhiteListMiddleware',
    'RedirectSchemeMiddleware',
    'RedirectRegexMiddleware',
    'BufferingMiddleware',
    'InFlightReqMiddleware',
    
    # Service Models
    'HealthCheck',
    'StickyCookie',
    'Server',
    'LoadBalancerService',
    'WeightedService',
    'MirrorService',
    'FailoverService',
    'Service',
    
    # TCP/UDP Models
    'TCPServer',
    'TCPService',
    'UDPServer',
    'UDPService',
    
    # TLS Models
    'TLSOptions',
    'TLSStore',
    
    # ServersTransport Models
    'ServersTransport',
    'TCPServersTransport',
    
    # Router Models
    'TLSConfig',
    'Observability',
    'Router',
    'TCPRouter',
    'UDPRouter',
    
    # Configuration Models
    'Domain',
    'GlobalConfig',
    
    # Helper Functions
    'middleware_from_dict',
    'middleware_to_dict',
    
    # Clients
    'ETCDClient',
    'ETCDException',
    'ConfigManager',
    'ValidationError',
]
