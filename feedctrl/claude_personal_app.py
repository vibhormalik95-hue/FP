"""Unactivated personal CLI app binding. Never selects a provider on import."""
from copy import deepcopy
import hmac
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit
from feedctrl.claude_personal import make_claude_personal_infer
from feedctrl.hosted_app import category_payload


def _personal_origin(value):
    if not isinstance(value,str):raise ValueError('Explicit loopback origin required')
    try:
        parsed=urlsplit(value);port=parsed.port
    except ValueError as exc:
        raise ValueError('Invalid loopback origin') from exc
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1','::1','localhost')
            or port is None or port == 80 or not 1 <= port <= 65535 or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('Explicit HTTP loopback host and non-default port required')
    host='[::1]' if parsed.hostname=='::1' else parsed.hostname
    expected=f'http://{host}:{port}'
    if value!=expected:raise ValueError('Canonical loopback origin required')
    return expected, f'{host}:{port}'


class PersonalBoundary:
    """Direct loopback, configured Host, narrow public UI and token-gated API.

    This is defense in depth, not OS-user isolation. Do not place behind a proxy;
    the actual server must disable proxy-header trust and bind only to the chosen host.
    """
    def __init__(self, app, token, origin, index_path, public_assets):
        self.app=app;self.token=token.encode('ascii')
        self.origin,self.host=_personal_origin(origin)
        self.index_path=Path(index_path);self.public_assets=frozenset(public_assets)

    async def _reject(self,scope,send):
        if scope['type']=='websocket':
            await send({'type':'websocket.close','code':1008})
        else:
            await send({'type':'http.response.start','status':403,'headers':[(b'cache-control',b'no-store')]})
            await send({'type':'http.response.body','body':b'Personal operator access required'})

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http','websocket'):
            return await self.app(scope,receive,send)
        try:
            peer=scope.get('client');headers=scope.get('headers',[])
            local=bool(peer and ipaddress.ip_address(peer[0]).is_loopback)
            hosts=[v for k,v in headers if k.lower()==b'host']
            origins=[v for k,v in headers if k.lower()==b'origin']
            tokens=[v for k,v in headers if k.lower()==b'x-personal-operator-token']
            fetch_sites=[v for k,v in headers if k.lower()==b'sec-fetch-site']
            forwarded=any(k.lower()==b'forwarded' or k.lower().startswith(b'x-forwarded-') for k,_ in headers)
            request_ok=(local and scope.get('scheme')=='http' and not forwarded and len(hosts)==1
                        and hosts[0]==self.host.encode('ascii') and len(origins)<=1
                        and (not origins or origins[0]==self.origin.encode('ascii'))
                        and len(fetch_sites)<=1)
        except (ValueError,TypeError,UnicodeError):
            request_ok=False
        if not request_ok:return await self._reject(scope,send)
        path=scope.get('path','');method=scope.get('method','')
        ui=scope['type']=='http' and method in ('GET','HEAD') and (path=='/' or path in self.public_assets)
        if not ui:
            if fetch_sites and fetch_sites[0] not in (b'same-origin',b'none'):
                return await self._reject(scope,send)
            if fetch_sites and method not in ('GET','HEAD') and not origins:
                return await self._reject(scope,send)
            if not (len(tokens)==1 and hmac.compare_digest(tokens[0],self.token)):
                return await self._reject(scope,send)
        async def safe_send(message):
            if message['type']=='http.response.start':
                headers=list(message.get('headers',[]))
                headers.extend([(b'cache-control',b'no-store'),(b'referrer-policy',b'no-referrer'),
                    (b'x-content-type-options',b'nosniff'),(b'x-frame-options',b'DENY'),
                    (b'content-security-policy',b"default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")])
                message={**message,'headers':headers}
            await send(message)
        if ui and path=='/':
            try:
                data=self.index_path.read_bytes()
                marker=b'<html lang="en">'
                if data.count(marker)!=1:raise ValueError('Unexpected frontend index')
                data=data.replace(marker,b'<html lang="en" data-personal-auth="required">',1)
            except (OSError,ValueError):
                await safe_send({'type':'http.response.start','status':503,'headers':[]})
                await safe_send({'type':'http.response.body','body':b'Personal UI unavailable'})
                return
            await safe_send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'text/html; charset=utf-8')]})
            await safe_send({'type':'http.response.body','body':b'' if method=='HEAD' else data})
            return
        return await self.app(scope,receive,safe_send)


def shared_personal_factories(infer, provenance):
    identity=deepcopy(provenance)
    if not callable(infer) or not isinstance(identity,dict) or identity.get('backend') != 'claude-code-personal-cli':
        raise ValueError('Explicit personal CLI transport required')
    for key in ('model','digest'):
        if not isinstance(identity.get(key),str) or not identity[key]:
            raise ValueError('Transport provenance required')
    # model_revision is a transport configuration digest, never a weights hash.
    category_identity={'backend':identity['backend'], 'model_id':identity['model'],
                       'model_revision':identity['digest']}
    def category_infer(payload,schema):
        return infer(category_payload(payload),deepcopy(schema))
    def semantic_factory():
        return infer,deepcopy(identity)
    def category_factory():
        return category_infer,deepcopy(category_identity)
    semantic_factory.model_identity=deepcopy(identity)
    return semantic_factory,category_factory


def create_claude_personal_app(*, operator_token, allowed_origin, data_path=None, semantic_path=None, fixture=False, **transport):
    """Create only after independent personal runtime, data, and usage review.

    This is not a launcher and does not configure a network listener. The caller
    must bind only to loopback and protect the token. Transport launch is disabled
    by default; a runner must be supplied explicitly.
    """
    if (not isinstance(operator_token,str) or len(operator_token)<32 or len(operator_token)>256
            or not operator_token.isascii() or any(c.isspace() for c in operator_token)):
        raise ValueError('A separately supplied personal operator token of at least 32 characters is required')
    _personal_origin(allowed_origin)
    infer, provenance, receipts=make_claude_personal_infer(**transport)
    semantic_factory,category_factory=shared_personal_factories(infer,provenance)
    from feedctrl.api import create_app, ROOT
    app=create_app(data_path=data_path,semantic_path=semantic_path,fixture=fixture,
                   semantic_infer_factory=semantic_factory,category_infer_factory=category_factory,
                   synthetic_infer_factory=semantic_factory,
                   allow_local_models=False,allow_local_recommender=False)
    dist=ROOT/'web'/'dist';assets=dist/'assets';public_assets=[]
    if assets.is_dir():
        for file in assets.rglob('*'):
            if file.is_file() and not file.is_symlink() and file.resolve().is_relative_to(assets.resolve()):
                public_assets.append('/assets/'+file.relative_to(assets).as_posix())
    app.add_middleware(PersonalBoundary,token=operator_token,origin=allowed_origin,
                       index_path=dist/'index.html',public_assets=public_assets)
    app.state.hosted_model_provenance=deepcopy(provenance)
    app.state.hosted_model_receipts=receipts
    return app
