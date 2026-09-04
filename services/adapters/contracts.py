from __future__ import annotations
from typing import Any
class AdapterError(ValueError): pass
ALLOWED={'project-file-import','mock-project-api'}
def validate_envelope(payload:dict[str,Any])->dict[str,Any]:
 if not isinstance(payload,dict) or payload.get('adapter') not in ALLOWED: raise AdapterError('适配器未启用')
 if payload.get('mode')!='simulation': raise AdapterError('没有真实授权时只允许 simulation 模式')
 if not isinstance(payload.get('records'),list): raise AdapterError('records 必须是列表')
 return {'adapter':payload['adapter'],'mode':'simulation','accepted_count':len(payload['records']),'writeback':False,'external_request_sent':False}
