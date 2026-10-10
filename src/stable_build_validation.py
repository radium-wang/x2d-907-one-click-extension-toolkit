"""Local stable speed packaging gates; never part of the camera runtime."""
import hashlib,json
from pathlib import Path
def require_tested_payload(payload,report):
 manifest=json.loads((payload/'speed-bundle.json').read_text())
 if not manifest.get('speedLevels'):return
 if report is None:raise RuntimeError('Stable speed packaging requires native UI evidence')
 ui=json.loads(Path(report).read_text());menu=ui.get('menuStyle',{});speed=menu.get('speedMenu',{})
 if ui.get('payloadManifestSha256')!=hashlib.sha256((payload/'speed-bundle.json').read_bytes()).hexdigest() or ui.get('visualMocks') is not False or ui.get('deviceAccessed') is not False:raise RuntimeError('Stable UI evidence does not match payload')
 if menu.get('selectionMasksVerified')!=7 or menu.get('existingRowsMatchBaseline') is not True or menu.get('speedImmediatelyBelowBoost') is not True:raise RuntimeError('Stable native row/mask checks incomplete')
 if speed.get('levels')!=['low','medium','high'] or speed.get('languages')!=['zh','zh-Hant','en'] or any(speed.get(k) is not True for k in ('selectionReadback','failureKeepsPreviousSelection','keyboardAndBack','disabledWhileOff','activeSelectionRetainsEnabled','nativeVerticalPicker','swipeNavigation','stockOrangeHighlight','userCommandOverridesPolling')):raise RuntimeError('Stable speed picker checks incomplete')
 machine=json.loads((payload/'speed-machine-validation.json').read_text())
 if machine.get('status')!='PASS' or machine.get('machineCodeCases')!=4206 or machine.get('deviceAccessed') is not False:raise RuntimeError('Stable machine-code checks incomplete')
 if {p['level']:p['sha256'] for p in machine['profiles']}!={k:v['sha256'] for k,v in manifest['speedLevels']['levels'].items()}:raise RuntimeError('Stable machine-code profile mismatch')
