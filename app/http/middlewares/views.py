"""app/http/middlewares/views.py — HTTP Middleware routes."""

from flask import render_template, request, redirect, url_for, flash

from app.http import bp
from app import globals as state
from app.utils import login_required, _parse_int, _parse_csv
from core.config_manager import ValidationError
from core.models import (
    MiddlewareType,
    AddPrefixMiddleware, StripPrefixMiddleware, StripPrefixRegexMiddleware,
    ReplacePathMiddleware, ReplacePathRegexMiddleware,
    HeadersMiddleware, RedirectSchemeMiddleware, RedirectRegexMiddleware,
    RateLimitMiddleware, CircuitBreakerMiddleware, RetryMiddleware,
    CompressMiddleware, BasicAuthMiddleware, DigestAuthMiddleware,
    ForwardAuthMiddleware, IPWhiteListMiddleware, BufferingMiddleware,
    InFlightReqMiddleware, ChainMiddleware, ContentTypeMiddleware,
    GrpcWebMiddleware, PassTLSClientCertMiddleware,
)


# ─── Helper ────────────────────────────────────────────────────────────────────

def _build_middleware_config(name: str, middleware_type: str, form):
    """
    Build (MiddlewareType enum, middleware dataclass) from submitted form data.
    Returns (None, None) with a flash message on validation failure.
    Raises ValueError with a message string on unknown type.
    """
    f = form  # shorthand

    if middleware_type == MiddlewareType.ADD_PREFIX.value:
        prefix = f.get('prefix', '').strip()
        if not prefix:
            flash('Prefix is required for addPrefix middleware.', 'danger')
            return None, None
        return MiddlewareType.ADD_PREFIX, AddPrefixMiddleware(name=name, type=MiddlewareType.ADD_PREFIX, prefix=prefix)

    if middleware_type == MiddlewareType.STRIP_PREFIX.value:
        prefixes = _parse_csv(f.get('prefixes', '').strip())
        if not prefixes:
            flash('At least one prefix is required for stripPrefix middleware.', 'danger')
            return None, None
        return MiddlewareType.STRIP_PREFIX, StripPrefixMiddleware(name=name, type=MiddlewareType.STRIP_PREFIX, prefixes=prefixes)

    if middleware_type == MiddlewareType.STRIP_PREFIX_REGEX.value:
        regex_list = _parse_csv(f.get('spr_regex', '').strip())
        if not regex_list:
            flash('At least one regex is required for stripPrefixRegex middleware.', 'danger')
            return None, None
        return MiddlewareType.STRIP_PREFIX_REGEX, StripPrefixRegexMiddleware(name=name, type=MiddlewareType.STRIP_PREFIX_REGEX, regex=regex_list)

    if middleware_type == MiddlewareType.REPLACE_PATH.value:
        path = f.get('rp_path', '').strip()
        if not path:
            flash('Path is required for replacePath middleware.', 'danger')
            return None, None
        return MiddlewareType.REPLACE_PATH, ReplacePathMiddleware(name=name, type=MiddlewareType.REPLACE_PATH, path=path)

    if middleware_type == MiddlewareType.REPLACE_PATH_REGEX.value:
        regex = f.get('rpr_regex', '').strip()
        if not regex:
            flash('Regex is required for replacePathRegex middleware.', 'danger')
            return None, None
        return MiddlewareType.REPLACE_PATH_REGEX, ReplacePathRegexMiddleware(
            name=name, type=MiddlewareType.REPLACE_PATH_REGEX,
            regex=regex, replacement=f.get('rpr_replacement', '').strip(),
        )

    if middleware_type == MiddlewareType.REDIRECT_SCHEME.value:
        scheme = f.get('scheme', '').strip()
        if not scheme:
            flash('Scheme is required for redirectScheme middleware.', 'danger')
            return None, None
        return MiddlewareType.REDIRECT_SCHEME, RedirectSchemeMiddleware(
            name=name, type=MiddlewareType.REDIRECT_SCHEME,
            scheme=scheme, permanent=f.get('permanent') == 'on',
        )

    if middleware_type == MiddlewareType.REDIRECT_REGEX.value:
        regex = f.get('rr_regex', '').strip()
        if not regex:
            flash('Regex is required for redirectRegex middleware.', 'danger')
            return None, None
        return MiddlewareType.REDIRECT_REGEX, RedirectRegexMiddleware(
            name=name, type=MiddlewareType.REDIRECT_REGEX,
            regex=regex, replacement=f.get('rr_replacement', '').strip(),
            permanent=f.get('rr_permanent') == 'on',
        )

    if middleware_type == MiddlewareType.RATE_LIMIT.value:
        average = _parse_int(f.get('average', ''), default=-1)
        burst   = _parse_int(f.get('burst', ''), default=-1)
        period  = f.get('period', '').strip()
        if average < 0:
            flash('Average must be a valid non-negative integer for rateLimit middleware.', 'danger')
            return None, None
        if burst < 0:
            flash('Burst must be a valid non-negative integer for rateLimit middleware.', 'danger')
            return None, None
        if not period:
            flash('Period is required for rateLimit middleware.', 'danger')
            return None, None
        return MiddlewareType.RATE_LIMIT, RateLimitMiddleware(
            name=name, type=MiddlewareType.RATE_LIMIT,
            average=average, burst=burst, period=period,
            use_ip_strategy='use_ip_strategy' in f,
            ip_depth=_parse_int(f.get('rl_ip_depth', '0'), default=0),
            excluded_ips=_parse_csv(f.get('rl_excluded_ips', '').strip()),
            use_request_host='use_request_host' in f,
            use_request_header=f.get('use_request_header', '').strip(),
        )

    if middleware_type == MiddlewareType.BASIC_AUTH.value:
        users = _parse_csv(f.get('users', '').strip())
        if not users:
            flash('At least one user entry is required for basicAuth middleware.', 'danger')
            return None, None
        for entry in users:
            if ':' not in entry:
                flash('Each basicAuth user must be in user:hashedpass format.', 'danger')
                return None, None
        return MiddlewareType.BASIC_AUTH, BasicAuthMiddleware(
            name=name, type=MiddlewareType.BASIC_AUTH,
            users=users, realm=f.get('realm', '').strip(),
            remove_header=f.get('remove_header') == 'on',
        )

    if middleware_type == MiddlewareType.DIGEST_AUTH.value:
        users = _parse_csv(f.get('dauth_users', '').strip())
        if not users:
            flash('At least one user entry is required for digestAuth middleware.', 'danger')
            return None, None
        return MiddlewareType.DIGEST_AUTH, DigestAuthMiddleware(
            name=name, type=MiddlewareType.DIGEST_AUTH,
            users=users, realm=f.get('dauth_realm', 'Restricted').strip(),
            remove_header=f.get('dauth_remove_header') == 'on',
        )

    if middleware_type == MiddlewareType.FORWARD_AUTH.value:
        address = f.get('fa_address', '').strip()
        if not address:
            flash('Address is required for forwardAuth middleware.', 'danger')
            return None, None
        return MiddlewareType.FORWARD_AUTH, ForwardAuthMiddleware(
            name=name, type=MiddlewareType.FORWARD_AUTH, address=address,
            trust_forward_header=f.get('fa_trust_forward') == 'on',
            auth_response_headers=_parse_csv(f.get('fa_response_headers', '')),
            tls_insecure_skip_verify=f.get('fa_tls_insecure') == 'on',
        )

    if middleware_type == MiddlewareType.IP_WHITELIST.value:
        source_range = _parse_csv(f.get('ip_source_range', '').strip())
        if not source_range:
            flash('At least one CIDR range is required for ipWhiteList middleware.', 'danger')
            return None, None
        return MiddlewareType.IP_WHITELIST, IPWhiteListMiddleware(
            name=name, type=MiddlewareType.IP_WHITELIST,
            source_range=source_range,
            ip_depth=_parse_int(f.get('ip_depth', '0'), default=0),
        )

    if middleware_type == MiddlewareType.HEADERS.value:
        return MiddlewareType.HEADERS, HeadersMiddleware(
            name=name, type=MiddlewareType.HEADERS,
            ssl_redirect=f.get('h_ssl_redirect') == 'on',
            sts_seconds=_parse_int(f.get('h_sts_seconds', '0'), default=0),
            sts_include_subdomains=f.get('h_sts_subdomains') == 'on',
            sts_preload=f.get('h_sts_preload') == 'on',
            force_sts_header=f.get('h_force_sts') == 'on',
            frame_deny=f.get('h_frame_deny') == 'on',
            content_type_nosniff=f.get('h_nosniff') == 'on',
            browser_xss_filter=f.get('h_xss_filter') == 'on',
            content_security_policy=f.get('h_csp', '').strip(),
            referrer_policy=f.get('h_referrer_policy', '').strip(),
            access_control_allow_credentials=f.get('h_cors_credentials') == 'on',
            access_control_allow_origin_list=_parse_csv(f.get('h_cors_origins', '')),
            access_control_allow_methods=_parse_csv(f.get('h_cors_methods', '')),
            access_control_allow_headers=_parse_csv(f.get('h_cors_headers', '')),
            access_control_max_age=_parse_int(f.get('h_cors_max_age', '0'), default=0),
        )

    if middleware_type == MiddlewareType.COMPRESS.value:
        return MiddlewareType.COMPRESS, CompressMiddleware(
            name=name, type=MiddlewareType.COMPRESS,
            excluded_content_types=_parse_csv(f.get('cmp_excluded', 'text/event-stream')),
            min_response_body_bytes=_parse_int(f.get('cmp_min_bytes', '1024'), default=1024),
        )

    if middleware_type == MiddlewareType.RETRY.value:
        return MiddlewareType.RETRY, RetryMiddleware(
            name=name, type=MiddlewareType.RETRY,
            attempts=_parse_int(f.get('retry_attempts', '4'), default=4),
            initial_interval=f.get('retry_interval', '100ms').strip() or '100ms',
        )

    if middleware_type == MiddlewareType.CIRCUIT_BREAKER.value:
        expression = f.get('cb_expression', '').strip()
        if not expression:
            flash('Expression is required for circuitBreaker middleware.', 'danger')
            return None, None
        return MiddlewareType.CIRCUIT_BREAKER, CircuitBreakerMiddleware(
            name=name, type=MiddlewareType.CIRCUIT_BREAKER,
            expression=expression,
            check_period=f.get('cb_check_period', '10s').strip() or '10s',
            fallback_duration=f.get('cb_fallback', '30s').strip() or '30s',
            recovery_duration=f.get('cb_recovery', '10s').strip() or '10s',
        )

    if middleware_type == MiddlewareType.BUFFERING.value:
        return MiddlewareType.BUFFERING, BufferingMiddleware(
            name=name, type=MiddlewareType.BUFFERING,
            max_request_body_bytes=_parse_int(f.get('buf_max_req', '2097152'), default=2097152),
            max_response_body_bytes=_parse_int(f.get('buf_max_resp', '2097152'), default=2097152),
            retry_expression=f.get('buf_retry_expr', '').strip(),
        )

    if middleware_type == MiddlewareType.IN_FLIGHT_REQ.value:
        return MiddlewareType.IN_FLIGHT_REQ, InFlightReqMiddleware(
            name=name, type=MiddlewareType.IN_FLIGHT_REQ,
            amount=_parse_int(f.get('ifr_amount', '10'), default=10),
        )

    if middleware_type == MiddlewareType.CHAIN.value:
        chain_mws = _parse_csv(f.get('chain_middlewares', '').strip())
        if not chain_mws:
            flash('At least one middleware is required for chain middleware.', 'danger')
            return None, None
        return MiddlewareType.CHAIN, ChainMiddleware(name=name, type=MiddlewareType.CHAIN, middlewares=chain_mws)

    if middleware_type == MiddlewareType.CONTENT_TYPE.value:
        return MiddlewareType.CONTENT_TYPE, ContentTypeMiddleware(
            name=name, type=MiddlewareType.CONTENT_TYPE,
            auto_detect=f.get('ct_auto_detect') == 'on',
        )

    if middleware_type == MiddlewareType.GRPC_WEB.value:
        return MiddlewareType.GRPC_WEB, GrpcWebMiddleware(
            name=name, type=MiddlewareType.GRPC_WEB,
            allow_origins=_parse_csv(f.get('grpc_origins', '*')),
        )

    if middleware_type == MiddlewareType.PASS_TLS_CLIENT_CERT.value:
        return MiddlewareType.PASS_TLS_CLIENT_CERT, PassTLSClientCertMiddleware(
            name=name, type=MiddlewareType.PASS_TLS_CLIENT_CERT,
            pem=f.get('ptcc_pem') == 'on',
        )

    raise ValueError(f'Unsupported middleware type: {middleware_type}')


# ─── HTTP Middlewares ──────────────────────────────────────────────────────────

@bp.route('/middlewares')
@login_required
def list_middlewares():
    """List all HTTP middlewares with their types."""
    cm = state.config_manager
    ec = state.etcd_client
    try:
        names = cm.list_middlewares()
        middleware_types = {}
        for mw_name in names:
            info = ec.get_http_middleware(mw_name)
            middleware_types[mw_name] = info[0].value if info else 'unknown'
        return render_template('http/middlewares/index.html', middlewares=names, middleware_types=middleware_types)
    except Exception as exc:
        flash(f'Error loading middlewares: {str(exc)}', 'danger')
        return render_template('http/middlewares/index.html', middlewares=[], middleware_types={})


@bp.route('/middlewares/<name>')
@login_required
def middleware_detail(name):
    """Show the type and raw config for a middleware."""
    try:
        info = state.etcd_client.get_http_middleware(name)
        if not info:
            flash(f'Middleware "{name}" not found.', 'warning')
            return render_template('http/middlewares/detail.html', middleware_name=name, middleware_type='unknown', middleware_config={})
        mw_type, mw_cfg = info
        return render_template(
            'http/middlewares/detail.html',
            middleware_name=name,
            middleware_type=mw_type.value,
            middleware_config=mw_cfg or {},
        )
    except Exception as exc:
        flash(f'Error loading middleware detail: {str(exc)}', 'danger')
        return render_template('http/middlewares/detail.html', middleware_name=name, middleware_type='unknown', middleware_config={})


@bp.route('/middlewares/create', methods=['GET', 'POST'])
@login_required
def create_middleware():
    """Create a new HTTP middleware."""
    if request.method == 'GET':
        return render_template('http/middlewares/create.html', form_data={})

    name            = request.form.get('name', '').strip()
    middleware_type = request.form.get('middleware_type', '').strip()

    if not name:
        flash('Middleware name is required.', 'danger')
        return render_template('http/middlewares/create.html', form_data=request.form)
    if not middleware_type:
        flash('Middleware type is required.', 'danger')
        return render_template('http/middlewares/create.html', form_data=request.form)

    try:
        cm = state.config_manager
        if cm.middleware_exists(name):
            flash(f'Middleware "{name}" already exists.', 'danger')
            return render_template('http/middlewares/create.html', form_data=request.form)

        mw_enum, mw_config = _build_middleware_config(name, middleware_type, request.form)
        if mw_enum is None:
            return render_template('http/middlewares/create.html', form_data=request.form)

        if cm.create_middleware(name, mw_enum, mw_config):
            flash(f'Middleware "{name}" created successfully!', 'success')
            return redirect(url_for('http.list_middlewares'))
        flash(f'Failed to create middleware "{name}".', 'danger')

    except ValueError as exc:
        flash(str(exc), 'danger')
    except ValidationError as exc:
        flash(f'Validation error: {str(exc)}', 'danger')
    except Exception as exc:
        flash(f'Error creating middleware: {str(exc)}', 'danger')

    return render_template('http/middlewares/create.html', form_data=request.form)


@bp.route('/middlewares/edit/<name>', methods=['GET', 'POST'])
@login_required
def edit_middleware(name):
    """Edit an existing HTTP middleware by overwriting it."""
    ec = state.etcd_client
    existing = ec.get_http_middleware(name)
    if not existing:
        flash(f'Middleware "{name}" not found.', 'warning')
        return redirect(url_for('http.list_middlewares'))

    middleware_type, middleware_config = existing

    _SUPPORTED = {
        MiddlewareType.ADD_PREFIX, MiddlewareType.STRIP_PREFIX,
        MiddlewareType.STRIP_PREFIX_REGEX, MiddlewareType.REPLACE_PATH,
        MiddlewareType.REPLACE_PATH_REGEX, MiddlewareType.REDIRECT_SCHEME,
        MiddlewareType.REDIRECT_REGEX, MiddlewareType.RATE_LIMIT,
        MiddlewareType.CIRCUIT_BREAKER, MiddlewareType.RETRY,
        MiddlewareType.COMPRESS, MiddlewareType.BASIC_AUTH,
        MiddlewareType.DIGEST_AUTH, MiddlewareType.FORWARD_AUTH,
        MiddlewareType.IP_WHITELIST, MiddlewareType.HEADERS,
        MiddlewareType.BUFFERING, MiddlewareType.IN_FLIGHT_REQ,
        MiddlewareType.CHAIN, MiddlewareType.CONTENT_TYPE,
        MiddlewareType.GRPC_WEB, MiddlewareType.PASS_TLS_CLIENT_CERT,
    }
    if middleware_type not in _SUPPORTED:
        flash(f'Middleware type "{middleware_type.value}" is not supported for editing in this UI.', 'warning')
        return redirect(url_for('http.list_middlewares'))

    cfg = middleware_config or {}

    if request.method == 'POST':
        try:
            mw_enum, mw_config = _build_middleware_config(name, middleware_type.value, request.form)
            if mw_enum is None:
                return render_template(
                    'http/middlewares/edit.html',
                    middleware_name=name,
                    middleware_type=middleware_type.value,
                    form_data=request.form,
                )
            if state.config_manager.create_middleware(name, middleware_type, mw_config):
                flash(f'Middleware "{name}" updated successfully!', 'success')
                return redirect(url_for('http.list_middlewares'))
            flash(f'Failed to update middleware "{name}".', 'danger')

        except ValueError as exc:
            flash(str(exc), 'danger')
        except ValidationError as exc:
            flash(f'Validation error: {str(exc)}', 'danger')
        except Exception as exc:
            flash(f'Error updating middleware: {str(exc)}', 'danger')

        return render_template(
            'http/middlewares/edit.html',
            middleware_name=name,
            middleware_type=middleware_type.value,
            form_data=request.form,
        )

    # ── GET: pre-populate form fields from stored config ─────────────────────
    def _csv(lst):
        return ', '.join(lst or [])

    form_data = {
        'middleware_type':  middleware_type.value,
        # addPrefix / stripPrefix
        'prefix':           cfg.get('prefix', ''),
        'prefixes':         _csv(cfg.get('prefixes', [])),
        'spr_regex':        _csv(cfg.get('regex', []) if isinstance(cfg.get('regex'), list) else []),
        # replacePath / replacePathRegex
        'rp_path':          cfg.get('path', ''),
        'rpr_regex':        cfg.get('regex', '') if not isinstance(cfg.get('regex'), list) else '',
        'rpr_replacement':  cfg.get('replacement', ''),
        # redirectScheme
        'scheme':           cfg.get('scheme', 'https'),
        'permanent':        cfg.get('permanent', True),
        # redirectRegex
        'rr_regex':         cfg.get('regex', '') if not isinstance(cfg.get('regex'), list) else '',
        'rr_replacement':   cfg.get('replacement', ''),
        'rr_permanent':     cfg.get('permanent', False),
        # rateLimit
        'average':          cfg.get('average', 100),
        'burst':            cfg.get('burst', 50),
        'period':           cfg.get('period', '1s'),
        'use_ip_strategy':  cfg.get('use_ip_strategy', True),
        'rl_ip_depth':      cfg.get('ip_depth', 0),
        'rl_excluded_ips':  _csv(cfg.get('excluded_ips', [])),
        'use_request_host': cfg.get('use_request_host', False),
        'use_request_header': cfg.get('use_request_header', ''),
        # retry
        'retry_attempts':   cfg.get('attempts', 4),
        'retry_interval':   cfg.get('initial_interval', '100ms'),
        # circuitBreaker
        'cb_expression':    cfg.get('expression', 'NetworkErrorRatio() > 0.30'),
        'cb_check_period':  cfg.get('check_period', '10s'),
        'cb_fallback':      cfg.get('fallback_duration', '30s'),
        'cb_recovery':      cfg.get('recovery_duration', '10s'),
        # compress
        'cmp_excluded':     _csv(cfg.get('excluded_content_types', ['text/event-stream'])),
        'cmp_min_bytes':    cfg.get('min_response_body_bytes', 1024),
        # basicAuth / digestAuth
        'users':            _csv(cfg.get('users', [])),
        'realm':            cfg.get('realm', 'Restricted'),
        'remove_header':    cfg.get('remove_header', False),
        'dauth_users':      _csv(cfg.get('users', [])),
        'dauth_realm':      cfg.get('realm', 'Restricted'),
        'dauth_remove_header': cfg.get('remove_header', False),
        # forwardAuth
        'fa_address':       cfg.get('address', ''),
        'fa_trust_forward': cfg.get('trust_forward_header', False),
        'fa_response_headers': _csv(cfg.get('auth_response_headers', [])),
        'fa_tls_insecure':  cfg.get('tls_insecure_skip_verify', False),
        # ipWhiteList
        'ip_source_range':  _csv(cfg.get('source_range', [])),
        'ip_depth':         cfg.get('ip_depth', 0),
        # headers security
        'h_ssl_redirect':   cfg.get('ssl_redirect', False),
        'h_sts_seconds':    cfg.get('sts_seconds', 0),
        'h_sts_subdomains': cfg.get('sts_include_subdomains', False),
        'h_sts_preload':    cfg.get('sts_preload', False),
        'h_force_sts':      cfg.get('force_sts_header', False),
        'h_frame_deny':     cfg.get('frame_deny', False),
        'h_nosniff':        cfg.get('content_type_nosniff', False),
        'h_xss_filter':     cfg.get('browser_xss_filter', False),
        'h_csp':            cfg.get('content_security_policy', ''),
        'h_referrer_policy':cfg.get('referrer_policy', ''),
        'h_cors_credentials': cfg.get('access_control_allow_credentials', False),
        'h_cors_origins':   _csv(cfg.get('access_control_allow_origin_list', [])),
        'h_cors_methods':   _csv(cfg.get('access_control_allow_methods', [])),
        'h_cors_headers':   _csv(cfg.get('access_control_allow_headers', [])),
        'h_cors_max_age':   cfg.get('access_control_max_age', 0),
        # buffering
        'buf_max_req':      cfg.get('max_request_body_bytes', 2097152),
        'buf_max_resp':     cfg.get('max_response_body_bytes', 2097152),
        'buf_retry_expr':   cfg.get('retry_expression', ''),
        # inFlightReq
        'ifr_amount':       cfg.get('amount', 10),
        # chain
        'chain_middlewares':_csv(cfg.get('middlewares', [])),
        # contentType
        'ct_auto_detect':   cfg.get('auto_detect', True),
        # grpcWeb
        'grpc_origins':     _csv(cfg.get('allow_origins', ['*'])),
        # passTLSClientCert
        'ptcc_pem':         cfg.get('pem', False),
    }
    return render_template(
        'http/middlewares/edit.html',
        middleware_name=name,
        middleware_type=middleware_type.value,
        form_data=form_data,
    )


@bp.route('/middlewares/delete/<name>', methods=['POST'])
@login_required
def delete_middleware(name):
    """Delete a middleware, blocked if referenced by any router."""
    cm = state.config_manager
    try:
        in_use = [r.name for r in cm.list_routers() if name in r.middlewares]
        if in_use:
            flash(f'Cannot delete middleware "{name}". Used by router(s): {", ".join(in_use)}', 'warning')
            return redirect(url_for('http.list_middlewares'))
        if cm.delete_middleware(name):
            flash(f'Middleware "{name}" deleted successfully!', 'success')
        else:
            flash(f'Failed to delete middleware "{name}".', 'danger')
    except ValidationError as exc:
        flash(f'Cannot delete middleware "{name}": {str(exc)}', 'warning')
    except Exception as exc:
        flash(f'Error deleting middleware: {str(exc)}', 'danger')
    return redirect(url_for('http.list_middlewares'))
