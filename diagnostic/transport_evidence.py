"""Bounded, content-free snapshots of existing transport projections."""
import math

MAX_EVENTS=4096
MAX_NUMBER=2**53-1
FRAMES=('assistant','result','stream_event','system','user','rate_limit_event')
EVENTS=('message_start','content_block_start','content_block_delta','content_block_stop','message_delta','message_stop','ping')
STOPS=('end_turn','max_tokens','stop_sequence','tool_use','pause_turn','refusal','model_context_window_exceeded')
SUBTYPES=('success','error_during_execution','error_max_turns','error_max_budget_usd','error_max_structured_output_retries')
USAGE=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
ERRORS=frozenset(('assistant_operational_failure','duplicate_key','incomplete_message','invalid_event_count',
 'invalid_event_order','invalid_frame','invalid_json','invalid_line_size','invalid_metadata','invalid_number',
 'invalid_rate_limit','invalid_status','invalid_stream_size','invalid_system_metadata','invalid_thinking_tokens',
 'missing_terminal','permission_denials_not_empty_or_missing','permission_mode_mismatch','rate_limit_rejected',
 'system_operational_failure','terminal_not_last','unsupported_content','unsupported_frame','unsupported_result',
 'unsupported_stop_reason','unsupported_stream_event','unsupported_system','projector_failed'))

def _counts(value,keys,limit):
 if type(value) is not dict:return None
 out={}
 for k in keys:
  if k in value:
   v=value[k]
   if type(v) is not int or not 0<=v<=limit:return None
   out[k]=v
 return out
def _terminal(value):
 if type(value) is not dict:return None
 subtype=value.get('subtype');flag=value.get('is_error');turns=value.get('num_turns');stop=value.get('stop_reason')
 if subtype not in SUBTYPES or type(flag) is not bool or type(turns) is not int or not 0<=turns<=MAX_NUMBER:
  return None
 if stop is not None and stop not in STOPS:return None
 usage=_counts(value.get('usage'),USAGE,MAX_NUMBER)
 out={'subtype':subtype,'is_error':flag,'num_turns':turns,'stop_reason':stop,'usage':usage}
 for key in ('duration_ms','duration_api_ms','queued_turn_count'):
  if key in value:
   v=value[key]
   if type(v) is int and 0<=v<=MAX_NUMBER:out[key]=v
 v=value.get('total_cost_usd')
 if type(v) in (int,float) and math.isfinite(v) and 0<=v<=1000000:out['estimated_cost_usd']=v
 return out
def _stop_counts(observation):
 if type(observation) is not dict or observation.get('scan_complete') is not True:return None
 section=observation.get('observed_response_and_stop_counts')
 if type(section) is not dict:return None
 part=section.get('message_delta_stop_reasons')
 if type(part) is not dict or type(part.get('finite_counts')) is not list:return None
 out={}
 for row in part['finite_counts']:
  if type(row) is not dict:continue
  kind=row.get('kind');count=row.get('count')
  if kind in STOPS and type(count) is int and 0<=count<=MAX_EVENTS and kind not in out:out[kind]=count
 return out
def _one(record):
 out={'projection_status':'unavailable','projection_error':None,'runner_returned':None,'runner_exit_code':None,
      'ordered_stop_reasons':None,'observed_stop_counts':None,'frame_counts':None,'stream_event_counts':None,
      'refusal_presence':'unavailable','intermediate_coverage':'unavailable','per_message_usage':None,
      'terminal':None,'unknown_system_seen':None,'unknown_rate_info_seen':None,'unknown_rate_top_seen':None}
 if type(record) is not dict:return out
 returned=record.get('runner_returned')
 if type(returned) is bool:out['runner_returned']=returned
 exit_code=record.get('runner_exit_code')
 if record.get('runner_exit_code_available') is True and type(exit_code) is int and -(2**31)<=exit_code<=2**32-1:
  out['runner_exit_code']=exit_code
 projection=record.get('projection')
 if type(projection) is not dict:return out
 if projection.get('ok') is True:
  out['projection_status']='accepted';out['intermediate_coverage']='unknown'
  out['refusal_presence']='not_observed_in_recognized_projection'
  stops=projection.get('intermediate_stop_reasons')
  if type(stops) is list and len(stops)<=MAX_EVENTS and all(type(s) is str and s in STOPS for s in stops):
   out['ordered_stop_reasons']=list(stops)
  out['frame_counts']=_counts(projection.get('frame_counts'),FRAMES,MAX_EVENTS)
  out['stream_event_counts']=_counts(projection.get('stream_event_counts'),EVENTS,MAX_EVENTS)
  out['terminal']=_terminal(projection.get('final_result'))
 elif projection.get('ok') is False:
  out['projection_status']='rejected';error=projection.get('error')
  out['projection_error']=error if type(error) is str and error in ERRORS else 'other'
  observation=record.get('rejection_observation');counts=_stop_counts(observation)
  out['observed_stop_counts']=counts
  out['refusal_presence']='observed_in_stop_reason' if counts is not None and counts.get('refusal',0)>0 else 'unavailable'
  if type(observation) is dict:out['terminal']=_terminal(observation.get('terminal_metadata'))
 else:return out
 for key in ('unknown_system_seen','unknown_rate_info_seen','unknown_rate_top_seen'):
  if type(projection.get(key)) is bool:out[key]=projection[key]
 return out
def snapshot(records):
 """Do not return raw frames, content, identifiers, paths, or arbitrary strings."""
 if type(records) is not list or len(records)>3:return {'capture_status':'unavailable','records':[]}
 try:return {'capture_status':'available','records':[_one(record) for record in records]}
 except Exception:return {'capture_status':'unavailable','records':[]}
