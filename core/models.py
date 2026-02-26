"""
Comprehensive data models for all Traefik entities

Supports:
- HTTP/TCP/UDP Routers
- All middleware types (20+)
- Advanced service configuration
- Health checks, sticky sessions, weights
- Complex routing rules
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Union
from datetime import datetime
from enum import Enum, auto


# ==================== Enums ====================

class Protocol(Enum):
    """Protocol type"""
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    UDP = "udp"
    WS = "ws"
    WSS = "wss"


class MiddlewareType(Enum):
    """All Traefik middleware types"""
    ADD_PREFIX = "addPrefix"
    STRIP_PREFIX = "stripPrefix"
    STRIP_PREFIX_REGEX = "stripPrefixRegex"
    REPLACE_PATH = "replacePath"
    REPLACE_PATH_REGEX = "replacePathRegex"
    HEADERS = "headers"
    RATE_LIMIT = "rateLimit"
    CIRCUIT_BREAKER = "circuitBreaker"
    RETRY = "retry"
    COMPRESS = "compress"
    BASIC_AUTH = "basicAuth"
    DIGEST_AUTH = "digestAuth"
    FORWARD_AUTH = "forwardAuth"
    IP_WHITELIST = "ipWhiteList"
    REDIRECT_SCHEME = "redirectScheme"
    REDIRECT_REGEX = "redirectRegex"
    CHAIN = "chain"
    BUFFERING = "buffering"
    IN_FLIGHT_REQ = "inFlightReq"
    PASS_TLS_CLIENT_CERT = "passTLSClientCert"
    CONTENT_TYPE = "contentType"
    GRPC_WEB = "grpcWeb"


class LoadBalancerMethod(Enum):
    """Load balancing algorithms"""
    ROUND_ROBIN = "roundrobin"
    WEIGHTED_ROUND_ROBIN = "wrr"


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class ServiceType(Enum):
    """Service types"""
    LOAD_BALANCER = "loadBalancer"
    WEIGHTED = "weighted"
    MIRRORING = "mirroring"
    FAILOVER = "failover"


class TCPMiddlewareType(Enum):
    """TCP middleware types"""
    IN_FLIGHT_CONN = "inFlightConn"
    IP_ALLOW_LIST = "ipAllowList"


# ==================== Middleware Models ====================

@dataclass
class MiddlewareBase:
    """Base class for all middlewares"""
    name: str
    type: MiddlewareType
    enabled: bool = True


@dataclass
class AddPrefixMiddleware(MiddlewareBase):
    """Add prefix to path"""
    prefix: str = "/"
    
    def __post_init__(self):
        self.type = MiddlewareType.ADD_PREFIX


@dataclass
class StripPrefixMiddleware(MiddlewareBase):
    """Strip prefix from path"""
    prefixes: List[str] = field(default_factory=lambda: ["/api"])
    force_slash: bool = True
    
    def __post_init__(self):
        self.type = MiddlewareType.STRIP_PREFIX


@dataclass
class HeadersMiddleware(MiddlewareBase):
    """Headers manipulation"""
    custom_request_headers: Dict[str, str] = field(default_factory=dict)
    custom_response_headers: Dict[str, str] = field(default_factory=dict)
    
    # Security headers
    ssl_redirect: bool = False
    sts_seconds: int = 0
    sts_include_subdomains: bool = False
    sts_preload: bool = False
    force_sts_header: bool = False
    frame_deny: bool = False
    custom_frame_options_value: str = ""
    content_type_nosniff: bool = False
    browser_xss_filter: bool = False
    custom_browser_xss_value: str = ""
    content_security_policy: str = ""
    referrer_policy: str = ""
    
    # CORS
    access_control_allow_credentials: bool = False
    access_control_allow_headers: List[str] = field(default_factory=list)
    access_control_allow_methods: List[str] = field(default_factory=list)
    access_control_allow_origin_list: List[str] = field(default_factory=list)
    access_control_expose_headers: List[str] = field(default_factory=list)
    access_control_max_age: int = 0
    
    def __post_init__(self):
        self.type = MiddlewareType.HEADERS


@dataclass
class RateLimitMiddleware(MiddlewareBase):
    """Rate limiting"""
    average: int = 100  # requests per period
    period: str = "1s"  # 1s, 1m, 1h
    burst: int = 50
    
    # Source criterion
    use_ip_strategy: bool = True
    ip_depth: int = 0  # X-Forwarded-For depth
    excluded_ips: List[str] = field(default_factory=list)
    use_request_host: bool = False
    use_request_header: str = ""
    
    def __post_init__(self):
        self.type = MiddlewareType.RATE_LIMIT


@dataclass
class CircuitBreakerMiddleware(MiddlewareBase):
    """Circuit breaker"""
    expression: str = "NetworkErrorRatio() > 0.30"
    check_period: str = "10s"
    fallback_duration: str = "30s"
    recovery_duration: str = "10s"
    
    def __post_init__(self):
        self.type = MiddlewareType.CIRCUIT_BREAKER


@dataclass
class RetryMiddleware(MiddlewareBase):
    """Retry failed requests"""
    attempts: int = 4
    initial_interval: str = "100ms"
    
    def __post_init__(self):
        self.type = MiddlewareType.RETRY


@dataclass
class CompressMiddleware(MiddlewareBase):
    """Response compression"""
    excluded_content_types: List[str] = field(default_factory=lambda: ["text/event-stream"])
    min_response_body_bytes: int = 1024
    
    def __post_init__(self):
        self.type = MiddlewareType.COMPRESS


@dataclass
class BasicAuthMiddleware(MiddlewareBase):
    """HTTP Basic authentication"""
    users: List[str] = field(default_factory=list)  # user:password (hashed)
    realm: str = "Restricted"
    remove_header: bool = False
    header_field: str = "X-WebAuth-User"
    
    def __post_init__(self):
        self.type = MiddlewareType.BASIC_AUTH


@dataclass
class DigestAuthMiddleware(MiddlewareBase):
    """HTTP Digest authentication"""
    users: List[str] = field(default_factory=list)  # user:realm:hash
    realm: str = "Restricted"
    remove_header: bool = False
    header_field: str = "X-WebAuth-User"
    
    def __post_init__(self):
        self.type = MiddlewareType.DIGEST_AUTH


@dataclass
class ForwardAuthMiddleware(MiddlewareBase):
    """Forward authentication to external service"""
    address: str = ""
    trust_forward_header: bool = False
    auth_response_headers: List[str] = field(default_factory=list)
    auth_response_headers_regex: str = ""
    auth_request_headers: List[str] = field(default_factory=list)
    tls_ca: str = ""
    tls_cert: str = ""
    tls_key: str = ""
    tls_insecure_skip_verify: bool = False
    
    def __post_init__(self):
        self.type = MiddlewareType.FORWARD_AUTH


@dataclass
class IPWhiteListMiddleware(MiddlewareBase):
    """IP whitelist"""
    source_range: List[str] = field(default_factory=list)  # CIDR ranges
    ip_depth: int = 0
    excluded_ips: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.type = MiddlewareType.IP_WHITELIST


@dataclass
class RedirectSchemeMiddleware(MiddlewareBase):
    """Redirect scheme (http -> https)"""
    scheme: str = "https"
    port: str = ""
    permanent: bool = True
    
    def __post_init__(self):
        self.type = MiddlewareType.REDIRECT_SCHEME


@dataclass
class RedirectRegexMiddleware(MiddlewareBase):
    """Redirect using regex"""
    regex: str = ""
    replacement: str = ""
    permanent: bool = False
    
    def __post_init__(self):
        self.type = MiddlewareType.REDIRECT_REGEX


@dataclass
class BufferingMiddleware(MiddlewareBase):
    """Request/response buffering"""
    max_request_body_bytes: int = 2097152  # 2MB
    mem_request_body_bytes: int = 1048576  # 1MB
    max_response_body_bytes: int = 2097152
    mem_response_body_bytes: int = 1048576
    retry_expression: str = ""
    
    def __post_init__(self):
        self.type = MiddlewareType.BUFFERING


@dataclass
class InFlightReqMiddleware(MiddlewareBase):
    """Limit concurrent requests"""
    amount: int = 10
    use_ip_strategy: bool = True
    ip_depth: int = 0
    use_request_host: bool = False
    
    def __post_init__(self):
        self.type = MiddlewareType.IN_FLIGHT_REQ


@dataclass
class StripPrefixRegexMiddleware(MiddlewareBase):
    """Strip prefix using regex"""
    regex: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.type = MiddlewareType.STRIP_PREFIX_REGEX


@dataclass
class ReplacePathMiddleware(MiddlewareBase):
    """Replace request path"""
    path: str = "/"

    def __post_init__(self):
        self.type = MiddlewareType.REPLACE_PATH


@dataclass
class ReplacePathRegexMiddleware(MiddlewareBase):
    """Replace request path using regex"""
    regex: str = ""
    replacement: str = ""

    def __post_init__(self):
        self.type = MiddlewareType.REPLACE_PATH_REGEX


@dataclass
class ChainMiddleware(MiddlewareBase):
    """Chain multiple middlewares"""
    middlewares: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.type = MiddlewareType.CHAIN


@dataclass
class ContentTypeMiddleware(MiddlewareBase):
    """Content-Type auto-detection"""
    auto_detect: bool = True

    def __post_init__(self):
        self.type = MiddlewareType.CONTENT_TYPE


@dataclass
class GrpcWebMiddleware(MiddlewareBase):
    """gRPC-Web protocol support"""
    allow_origins: List[str] = field(default_factory=lambda: ["*"])

    def __post_init__(self):
        self.type = MiddlewareType.GRPC_WEB


@dataclass
class PassTLSClientCertMiddleware(MiddlewareBase):
    """Pass TLS client certificate info to headers"""
    pem: bool = False

    def __post_init__(self):
        self.type = MiddlewareType.PASS_TLS_CLIENT_CERT


# ==================== Observability Model ====================

@dataclass
class Observability:
    """Router-level observability settings"""
    access_logs: bool = True
    metrics: bool = True
    tracing: bool = True


# ==================== Service Models ====================

@dataclass
class HealthCheck:
    """Health check configuration"""
    path: str = "/health"
    interval: str = "10s"
    timeout: str = "3s"
    scheme: str = "http"
    port: int = 0  # 0 = use service port
    hostname: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    follow_redirects: bool = True
    method: str = "GET"
    status: int = 0  # expected status code, 0 = default


@dataclass
class StickyCookie:
    """Sticky session cookie configuration"""
    name: str = "lb"
    secure: bool = False
    http_only: bool = True
    same_site: str = "lax"  # none, lax, strict
    max_age: int = 0
    path: str = ""


@dataclass
class Server:
    """Backend server"""
    url: str
    weight: int = 1
    preserve_path: bool = False


@dataclass
class LoadBalancerService:
    """Load balancer service"""
    servers: List[Server] = field(default_factory=list)
    health_check: Optional[HealthCheck] = None
    sticky: Optional[StickyCookie] = None
    pass_host_header: bool = True
    response_forwarding_flush_interval: str = "100ms"
    servers_transport: str = ""


@dataclass
class WeightedService:
    """Weighted service (A/B testing, canary)"""
    name: str
    weight: int = 100


@dataclass
class MirrorService:
    """Mirror service (traffic mirroring)"""
    name: str
    percent: int = 100


@dataclass
class FailoverService:
    """Failover service configuration"""
    service: str = ""
    fallback: str = ""
    health_check: Optional[Dict[str, Any]] = None


@dataclass
class Service:
    """Traefik service"""
    name: str
    type: ServiceType = ServiceType.LOAD_BALANCER
    
    # LoadBalancer type
    load_balancer: Optional[LoadBalancerService] = None
    
    # Weighted type
    weighted_services: List[WeightedService] = field(default_factory=list)
    weighted_sticky: Optional[StickyCookie] = None
    
    # Mirroring type
    mirroring_service: str = ""
    mirrors: List[MirrorService] = field(default_factory=list)
    
    # Failover type
    failover: Optional[FailoverService] = None


# ==================== Router Models ====================

@dataclass
class TLSConfig:
    """TLS configuration"""
    cert_resolver: str = ""
    options: str = ""
    domains: List[Dict[str, Union[str, List[str]]]] = field(default_factory=list)
    # domains format: [{"main": "example.com", "sans": ["www.example.com", "api.example.com"]}]


@dataclass
class Router:
    """HTTP Router"""
    name: str
    rule: str
    service: str
    entrypoints: List[str] = field(default_factory=lambda: ["websecure"])
    middlewares: List[str] = field(default_factory=list)
    priority: int = 0
    tls: Optional[TLSConfig] = None
    observability: Optional[Observability] = None
    
    # Metadata (not stored in etcd)
    health_status: HealthStatus = HealthStatus.UNKNOWN
    response_time_ms: int = 0
    last_checked: Optional[datetime] = None
    tags: Set[str] = field(default_factory=set)


@dataclass
class TCPRouter:
    """TCP Router"""
    name: str
    rule: str = "HostSNI(`*`)"
    service: str = ""
    entrypoints: List[str] = field(default_factory=lambda: ["tcp"])
    middlewares: List[str] = field(default_factory=list)
    tls: Optional[TLSConfig] = None
    tls_passthrough: bool = False
    tls_options: str = ""
    priority: int = 0


@dataclass
class UDPRouter:
    """UDP Router"""
    name: str
    service: str
    entrypoints: List[str] = field(default_factory=lambda: ["udp"])


# ==================== TCP/UDP Service Models ====================

@dataclass
class TCPServer:
    """TCP backend server"""
    address: str
    tls: bool = False


@dataclass
class TCPService:
    """TCP Service"""
    name: str
    servers: List[TCPServer] = field(default_factory=list)
    servers_transport: str = ""
    # Weighted
    weighted_services: List[WeightedService] = field(default_factory=list)


@dataclass
class UDPServer:
    """UDP backend server"""
    address: str


@dataclass
class UDPService:
    """UDP Service"""
    name: str
    servers: List[UDPServer] = field(default_factory=list)
    # Weighted
    weighted_services: List[WeightedService] = field(default_factory=list)


# ==================== TLS Options & Stores ====================

@dataclass
class TLSOptions:
    """TLS Options configuration"""
    name: str
    min_version: str = ""
    max_version: str = ""
    cipher_suites: List[str] = field(default_factory=list)
    curve_preferences: List[str] = field(default_factory=list)
    sni_strict: bool = False
    alpn_protocols: List[str] = field(default_factory=list)
    client_auth_type: str = ""
    client_auth_ca_files: List[str] = field(default_factory=list)
    disable_session_tickets: bool = False


@dataclass
class TLSStore:
    """TLS Store with default generated cert"""
    name: str
    default_certificate_cert: str = ""
    default_certificate_key: str = ""
    default_generated_cert_resolver: str = ""
    default_generated_cert_domain_main: str = ""
    default_generated_cert_domain_sans: List[str] = field(default_factory=list)


# ==================== ServersTransport ====================

@dataclass
class ServersTransport:
    """HTTP ServersTransport configuration"""
    name: str
    server_name: str = ""
    insecure_skip_verify: bool = False
    root_cas: List[str] = field(default_factory=list)
    max_idle_conns_per_host: int = 0
    disable_http2: bool = False
    peer_cert_uri: str = ""
    certificates: List[dict] = field(default_factory=list)
    forwarding_timeouts: dict = field(default_factory=dict)
    spiffe: dict = field(default_factory=dict)
    # Legacy individual timeout fields (kept for backwards compat)
    forwarding_timeouts_dial_timeout: str = ""
    forwarding_timeouts_response_header_timeout: str = ""
    forwarding_timeouts_idle_conn_timeout: str = ""


@dataclass
class TCPServersTransport:
    """TCP ServersTransport configuration"""
    name: str
    tls_insecure_skip_verify: bool = False
    tls_root_cas: List[str] = field(default_factory=list)
    tls_server_name: str = ""
    dial_timeout: str = ""
    dial_keep_alive: str = ""


# ====================  Domain & Configuration ====================

@dataclass
class Domain:
    """Registered domain"""
    name: str
    cert_resolver: str = ""
    is_default: bool = False
    sans: List[str] = field(default_factory=list)


@dataclass
class GlobalConfig:
    """Global configuration"""
    domains: List[Domain] = field(default_factory=list)
    default_cert_resolver: str = "letsencrypt"
    default_entrypoint: str = "websecure"
    default_middlewares: List[str] = field(default_factory=list)
    
    # Health check defaults
    default_health_endpoint: str = "/health"
    default_health_interval: str = "10s"
    default_health_timeout: str = "3s"


# ==================== Helper Functions ====================

def middleware_from_dict(data: Dict[str, Any]) -> Optional[MiddlewareBase]:
    """Create middleware instance from dictionary"""
    mw_type = MiddlewareType(data.get("type"))
    name = data.get("name", "")
    
    if mw_type == MiddlewareType.ADD_PREFIX:
        return AddPrefixMiddleware(name=name, prefix=data.get("prefix", "/"))
    elif mw_type == MiddlewareType.STRIP_PREFIX:
        return StripPrefixMiddleware(
            name=name,
            prefixes=data.get("prefixes", ["/api"]),
            force_slash=data.get("force_slash", True)
        )
    elif mw_type == MiddlewareType.HEADERS:
        return HeadersMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.RATE_LIMIT:
        return RateLimitMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.CIRCUIT_BREAKER:
        return CircuitBreakerMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.RETRY:
        return RetryMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.COMPRESS:
        return CompressMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.BASIC_AUTH:
        return BasicAuthMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.DIGEST_AUTH:
        return DigestAuthMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.FORWARD_AUTH:
        return ForwardAuthMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.IP_WHITELIST:
        return IPWhiteListMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.REDIRECT_SCHEME:
        return RedirectSchemeMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.REDIRECT_REGEX:
        return RedirectRegexMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.BUFFERING:
        return BufferingMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    elif mw_type == MiddlewareType.IN_FLIGHT_REQ:
        return InFlightReqMiddleware(name=name, **{k: v for k, v in data.items() if k not in ["name", "type"]})
    
    return None


def middleware_to_dict(middleware: MiddlewareBase) -> Dict[str, Any]:
    """Convert middleware to dictionary for storage"""
    result = {
        "name": middleware.name,
        "type": middleware.type.value,
        "enabled": middleware.enabled
    }
    
    # Add type-specific fields
    if isinstance(middleware, AddPrefixMiddleware):
        result["prefix"] = middleware.prefix
    elif isinstance(middleware, StripPrefixMiddleware):
        result["prefixes"] = middleware.prefixes
        result["force_slash"] = middleware.force_slash
    elif isinstance(middleware, RedirectSchemeMiddleware):
        result["scheme"] = middleware.scheme
        result["port"] = middleware.port
        result["permanent"] = middleware.permanent
    elif isinstance(middleware, HeadersMiddleware):
        result.update({k: v for k, v in middleware.__dict__.items() if k not in ["name", "type", "enabled"]})
    elif isinstance(middleware, RateLimitMiddleware):
        result.update({
            "average": middleware.average,
            "period": middleware.period,
            "burst": middleware.burst,
            "use_ip_strategy": middleware.use_ip_strategy,
            "ip_depth": middleware.ip_depth,
            "excluded_ips": middleware.excluded_ips,
            "use_request_host": middleware.use_request_host,
            "use_request_header": middleware.use_request_header
        })
    elif isinstance(middleware, BasicAuthMiddleware):
        result.update({
            "users": middleware.users,
            "realm": middleware.realm,
            "remove_header": middleware.remove_header,
            "header_field": middleware.header_field,
        })
    elif isinstance(middleware, DigestAuthMiddleware):
        result.update({
            "users": middleware.users,
            "realm": middleware.realm,
            "remove_header": middleware.remove_header,
            "header_field": middleware.header_field,
        })
    elif isinstance(middleware, ForwardAuthMiddleware):
        result.update({
            "address": middleware.address,
            "trust_forward_header": middleware.trust_forward_header,
            "auth_response_headers": middleware.auth_response_headers,
            "auth_response_headers_regex": middleware.auth_response_headers_regex,
            "auth_request_headers": middleware.auth_request_headers,
            "tls_ca": middleware.tls_ca,
            "tls_cert": middleware.tls_cert,
            "tls_key": middleware.tls_key,
            "tls_insecure_skip_verify": middleware.tls_insecure_skip_verify,
        })
    elif isinstance(middleware, IPWhiteListMiddleware):
        result.update({
            "source_range": middleware.source_range,
            "ip_depth": middleware.ip_depth,
            "excluded_ips": middleware.excluded_ips,
        })
    elif isinstance(middleware, RedirectRegexMiddleware):
        result.update({
            "regex": middleware.regex,
            "replacement": middleware.replacement,
            "permanent": middleware.permanent,
        })
    elif isinstance(middleware, CircuitBreakerMiddleware):
        result.update({
            "expression": middleware.expression,
            "check_period": middleware.check_period,
            "fallback_duration": middleware.fallback_duration,
            "recovery_duration": middleware.recovery_duration,
        })
    elif isinstance(middleware, RetryMiddleware):
        result.update({
            "attempts": middleware.attempts,
            "initial_interval": middleware.initial_interval,
        })
    elif isinstance(middleware, CompressMiddleware):
        result.update({
            "excluded_content_types": middleware.excluded_content_types,
            "min_response_body_bytes": middleware.min_response_body_bytes,
        })
    elif isinstance(middleware, BufferingMiddleware):
        result.update({
            "max_request_body_bytes": middleware.max_request_body_bytes,
            "mem_request_body_bytes": middleware.mem_request_body_bytes,
            "max_response_body_bytes": middleware.max_response_body_bytes,
            "mem_response_body_bytes": middleware.mem_response_body_bytes,
            "retry_expression": middleware.retry_expression,
        })
    elif isinstance(middleware, InFlightReqMiddleware):
        result.update({
            "amount": middleware.amount,
            "use_ip_strategy": middleware.use_ip_strategy,
            "ip_depth": middleware.ip_depth,
            "use_request_host": middleware.use_request_host,
        })
    elif isinstance(middleware, StripPrefixRegexMiddleware):
        result["regex"] = middleware.regex
    elif isinstance(middleware, ReplacePathMiddleware):
        result["path"] = middleware.path
    elif isinstance(middleware, ReplacePathRegexMiddleware):
        result.update({"regex": middleware.regex, "replacement": middleware.replacement})
    elif isinstance(middleware, ChainMiddleware):
        result["middlewares"] = middleware.middlewares
    elif isinstance(middleware, ContentTypeMiddleware):
        result["autoDetect"] = middleware.auto_detect
    elif isinstance(middleware, GrpcWebMiddleware):
        result["allowOrigins"] = middleware.allow_origins
    elif isinstance(middleware, PassTLSClientCertMiddleware):
        result["pem"] = middleware.pem

    return result
