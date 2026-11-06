"""Conditional per-run spending guard. No credentials or network implementation.

Pricing/counter/account evidence must be independently established before live
use. Hashes identify that evidence; this module does not prove it true. The
fixed owned ledger is not an account-wide cap or defense against file rollback,
cloning/deletion, bypassing this adapter, or dishonest provider billing.
"""
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from feedctrl.controls import ParserOperationalError
from feedctrl.indirect_grounding import _response_snapshot

TOTAL_MICRO_USD=500000
ATTEMPT_MICRO_USD=250000
MAX_ATTEMPTS=2

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def is_hash(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None

def validate_policy(value):
    keys={'run_id','model','reasoning_effort','allowed_request_sha256',
          'max_input_tokens','max_output_tokens','input_usd_per_million',
          'output_usd_per_million','counter_upper_micro_usd','other_upper_micro_usd',
          'price_evidence_sha256','counter_evidence_sha256','account_evidence_sha256'}
    if not isinstance(value,dict) or set(value)!=keys:raise ValueError('Complete locked spending policy required')
    p=deepcopy(value)
    if (not isinstance(p['run_id'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,100}',p['run_id'])
            or p['model']!='gpt-6.1-sol' or p['reasoning_effort']!='medium'):
        raise ValueError('Only the approved exact model/effort/run is supported')
    allowed=p['allowed_request_sha256']
    if not isinstance(allowed,list) or not 1<=len(allowed)<=2 or not all(is_hash(x) for x in allowed) or len(set(allowed))!=len(allowed):
        raise ValueError('One or two frozen exact request hashes required')
    for key in ('price_evidence_sha256','counter_evidence_sha256','account_evidence_sha256'):
        if not is_hash(p[key]):raise ValueError('External evidence identity required; no implied verification')
    for key,maximum in [('max_input_tokens',16000),('max_output_tokens',4096)]:
        if type(p[key]) is not int or not 1<=p[key]<=maximum:raise ValueError('Invalid locked token cap')
    for key in ('counter_upper_micro_usd','other_upper_micro_usd'):
        if type(p[key]) is not int or not 0<=p[key]<=ATTEMPT_MICRO_USD:raise ValueError('A proven nonnegative charge bound is required')
    rates=[]
    for key,floor in [('input_usd_per_million',5),('output_usd_per_million',10)]:
        if not isinstance(p[key],str):raise ValueError('Exact rational price strings required')
        try:rate=Fraction(p[key])
        except (ValueError,ZeroDivisionError) as exc:raise ValueError('Invalid exact price') from exc
        if rate<floor:raise ValueError('Rate below this run conservative pricing floor')
        rates.append(rate)
    bound=p['max_input_tokens']*rates[0]+p['max_output_tokens']*rates[1]
    bound=(bound.numerator+bound.denominator-1)//bound.denominator
    if bound+p['counter_upper_micro_usd']+p['other_upper_micro_usd']>ATTEMPT_MICRO_USD:
        raise ValueError('Worst-case count/generation/extras exceed one reserved slot')
    return p

class DurableHostedSpendGuard:
    """Two permanent $0.25 reservations, before any counter invocation.

    Constructor never creates a missing ledger. Use create_new exactly once for
    a separately authorized run; use open_existing after a restart. An in-flight
    reservation cannot resume or expire. No refunds or automatic retries exist.
    counter(bytes) must itself have verified one-attempt/no-redirect behavior and
    an independently proven billing bound. This class invokes it at most once
    per reservation but cannot constrain arbitrary callback internals.
    """
    def __init__(self,path,policy,counter):
        self.path=Path(path).resolve()
        self._policy=validate_policy(policy)
        if not callable(counter):raise ValueError('Verified complete-payload counter callable required')
        self.counter=counter
        self.spec={'path':str(self.path),'policy':deepcopy(self._policy),'total_micro_usd':TOTAL_MICRO_USD,
                   'attempt_micro_usd':ATTEMPT_MICRO_USD,'max_attempts':MAX_ATTEMPTS}
        self.binding_sha256=digest(self.spec)
        with self._connection() as db:self._check(db)

    @property
    def policy(self):return deepcopy(self._policy)

    @classmethod
    def create_new(cls,path,policy,counter):
        p=validate_policy(policy);path=Path(path).resolve()
        if not callable(counter):raise ValueError('Verified counter callable required')
        # Partial initialization intentionally leaves a non-reusable file.
        try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        except FileExistsError as exc:raise ValueError('Run ledger already exists; never reinitialize') from exc
        except OSError as exc:raise ParserOperationalError('Cannot create the owned run ledger') from exc
        try:os.fsync(fd)
        finally:os.close(fd)
        spec={'path':str(path),'policy':p,'total_micro_usd':TOTAL_MICRO_USD,
              'attempt_micro_usd':ATTEMPT_MICRO_USD,'max_attempts':MAX_ATTEMPTS}
        with cls._configured_connection(path) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE run (binding TEXT NOT NULL, spec TEXT NOT NULL, blocked INTEGER NOT NULL CHECK(blocked IN (0,1)))')
            db.execute("CREATE TABLE attempts (slot INTEGER PRIMARY KEY CHECK(slot IN (1,2)), request_sha TEXT NOT NULL UNIQUE, reserved INTEGER NOT NULL CHECK(reserved=250000), state TEXT NOT NULL CHECK(state IN ('reserved','counted','completed','failed')), proof TEXT)")
            db.execute('INSERT INTO run VALUES (?,?,0)',(digest(spec),canonical(spec).decode()))
            db.commit()
        return cls(path,p,counter)

    @classmethod
    def open_existing(cls,path,policy,counter):return cls(path,policy,counter)

    @staticmethod
    @contextmanager
    def _configured_connection(path):
        db=None
        try:
            # mode=rw never silently recreates a lost/renamed ledger.
            db=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2,isolation_level=None)
            if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0].lower()!='delete':
                raise ValueError('Ledger journal mode unavailable')
            db.execute('PRAGMA synchronous=EXTRA')
            if db.execute('PRAGMA synchronous').fetchone()[0]!=3:raise ValueError('Ledger EXTRA durability unavailable')
            yield db
        except (sqlite3.Error,OSError) as exc:
            raise ParserOperationalError('Spending ledger unavailable; no further transmission') from exc
        finally:
            if db is not None:db.close()

    def _connection(self):
        if not self.path.is_file():raise ParserOperationalError('Existing spending ledger required; no recreation')
        return self._configured_connection(self.path)

    def _check(self,db):
        run=db.execute('SELECT binding,spec,blocked FROM run').fetchall()
        if len(run)!=1 or run[0][:2]!=(self.binding_sha256,canonical(self.spec).decode()) or run[0][2] not in (0,1):
            raise ValueError('Spending ledger does not match locked run/configuration')
        rows=db.execute('SELECT slot,request_sha,reserved,state FROM attempts ORDER BY slot').fetchall()
        if ([r[0] for r in rows]!=list(range(1,len(rows)+1)) or len(rows)>MAX_ATTEMPTS
                or any(r[1] not in self.policy['allowed_request_sha256'] or r[2]!=ATTEMPT_MICRO_USD
                       or r[3] not in ('reserved','counted','completed','failed') for r in rows)):
            raise ValueError('Spending ledger is inconsistent')
        return run[0][2],rows

    def validate_transport(self,config):
        if (config.get('backend')!='openai-responses'
                or config.get('endpoint')!='https://api.openai.com/v1/responses'
                or config.get('store') is not False or config.get('retries')!=0 or config.get('tools')!=[]
                or config.get('model')!=self.policy['model']
                or config.get('reasoning_effort')!=self.policy['reasoning_effort']
                or config.get('service_tier')!='default'
                or config.get('max_output_tokens')!=self.policy['max_output_tokens']
                or type(config.get('max_calls')) is not int or not 1<=config['max_calls']<=MAX_ATTEMPTS
                or type(config.get('max_request_bytes')) is not int or not 1<=config['max_request_bytes']<=20000):
            raise ValueError('Transport differs from locked spending policy')

    def _reserve(self,request_sha):
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE');blocked,rows=self._check(db)
            if blocked or any(r[3] in ('reserved','counted','failed') for r in rows):
                raise ParserOperationalError('Run blocked or attempt in flight; no resume/retry')
            if len(rows)>=MAX_ATTEMPTS or any(r[1]==request_sha for r in rows):
                raise ParserOperationalError('Permanent spending allowance exhausted or duplicate attempt')
            slot=len(rows)+1
            db.execute('INSERT INTO attempts VALUES (?,?,?,\'reserved\',NULL)',(slot,request_sha,ATTEMPT_MICRO_USD))
            db.commit()  # must succeed before counter/network may run
        return {'slot':slot,'request_sha256':request_sha,'binding_sha256':self.binding_sha256,
                'reserved_micro_usd':ATTEMPT_MICRO_USD}

    def _update(self,ticket,state,proof=None):
        if ticket.get('binding_sha256')!=self.binding_sha256:raise ValueError('Reservation belongs to another run')
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE');self._check(db)
            row=db.execute('SELECT request_sha,state FROM attempts WHERE slot=?',(ticket['slot'],)).fetchone()
            if not row or row[0]!=ticket['request_sha256']:raise ValueError('Reservation mismatch')
            if state!='failed' and row[1]!=('reserved' if state=='counted' else 'counted'):
                raise ValueError('Reservation cannot be reused or resumed')
            db.execute('UPDATE attempts SET state=?,proof=COALESCE(?,proof) WHERE slot=?',
                       (state,canonical(proof).decode() if proof is not None else None,ticket['slot']))
            if state=='failed':db.execute('UPDATE run SET blocked=1')
            db.commit()

    def before_send(self,request_bytes):
        if type(request_bytes) is not bytes or len(request_bytes)>20000:raise ValueError('Bounded immutable request bytes required')
        try:body=_response_snapshot(json.loads(request_bytes))
        except (ValueError,RecursionError) as exc:raise ValueError('Invalid canonical request JSON') from exc
        if (not isinstance(body,dict) or canonical(body)!=request_bytes or set(body)!={'model','store','stream','service_tier','reasoning','max_output_tokens','input','text'}
                or body['model']!=self.policy['model'] or body['service_tier']!='default'
                or body['store'] is not False or body['stream'] is not False
                or body['reasoning']!={'effort':'medium'} or type(body['max_output_tokens']) is not int or body['max_output_tokens']!=self.policy['max_output_tokens']
                or not isinstance(body['input'],list) or len(body['input'])!=2
                or not all(isinstance(m,dict) for m in body['input'])
                or [m.get('role') for m in body['input']]!=['system','user']
                or any(set(m)!={'role','content'} or not isinstance(m['content'],str) for m in body['input'])):
            raise ValueError('Only the locked text/schema default-tier request is permitted')
        text=body['text'];format=text.get('format') if isinstance(text,dict) else None
        if (not isinstance(text,dict) or set(text)!={'format'} or not isinstance(format,dict)
                or set(format)!={'type','name','strict','schema'} or format['type']!='json_schema'
                or format['name']!='feed_control' or format['strict'] is not True
                or not isinstance(format['schema'],dict) or format['schema'].get('type')!='object'):
            raise ValueError('Only the locked object JSON-schema output is supported')
        request_sha=hashlib.sha256(request_bytes).hexdigest()
        if request_sha not in self.policy['allowed_request_sha256']:raise ValueError('Request bytes were not frozen for this run')
        ticket=self._reserve(request_sha)
        try:
            proof=self.counter(request_bytes)
            if (not isinstance(proof,dict) or set(proof)!={'request_sha256','model','input_tokens','counter_receipt_sha256'}
                    or proof['request_sha256']!=request_sha or proof['model']!=self.policy['model']
                    or type(proof['input_tokens']) is not int or not 1<=proof['input_tokens']<=self.policy['max_input_tokens']
                    or not is_hash(proof['counter_receipt_sha256'])):
                raise ValueError('Complete-payload count proof is invalid or over budget')
            cost=proof['input_tokens']*Fraction(self.policy['input_usd_per_million'])+self.policy['max_output_tokens']*Fraction(self.policy['output_usd_per_million'])
            upper=(cost.numerator+cost.denominator-1)//cost.denominator+self.policy['counter_upper_micro_usd']+self.policy['other_upper_micro_usd']
            if upper>ATTEMPT_MICRO_USD:raise ValueError('Count/generation/extras exceed reservation')
            ticket.update(input_tokens=proof['input_tokens'],upper_micro_usd=upper,
                          counter_receipt_sha256=proof['counter_receipt_sha256'])
            self._update(ticket,'counted',ticket)
            return deepcopy(ticket)
        except Exception as exc:
            error=ParserOperationalError('Spending preflight failed; no generation, reservation retained')
            raise self._fail_retaining_error(ticket,error) from exc

    def complete(self,ticket,response):
        usage=response.get('usage') if isinstance(response,dict) else None
        if (not isinstance(usage,dict) or response.get('model')!=self.policy['model']
                or response.get('service_tier')!='default'
                or type(usage.get('input_tokens')) is not int
                or not 0<=usage['input_tokens']<=ticket['input_tokens']
                or type(usage.get('output_tokens')) is not int
                or not 0<=usage['output_tokens']<=self.policy['max_output_tokens']):
            error=ParserOperationalError('Unexpected model/tier/usage; run blocked, reservation retained')
            raise self._fail_retaining_error(ticket,error)
        self._update(ticket,'completed')  # no refund, even on cheap completion

    def fail(self,ticket):self._update(ticket,'failed')

    def _fail_retaining_error(self,ticket,error):
        try:self.fail(ticket)
        except Exception as persistence_error:
            # A prior committed reservation still prevents reuse. Do not let
            # secondary persistence failure erase the primary failure evidence.
            error.guard_persistence_error_type=type(persistence_error).__name__
        return error

    def snapshot(self):
        with self._connection() as db:
            blocked,rows=self._check(db)
        return {'binding_sha256':self.binding_sha256,'blocked':bool(blocked),
                'attempts':[{'slot':r[0],'request_sha256':r[1],'reserved_micro_usd':r[2],'state':r[3]} for r in rows],
                'reserved_micro_usd':sum(r[2] for r in rows),'ceiling_micro_usd':TOTAL_MICRO_USD}
