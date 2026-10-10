"""Offline three-level speed bundle and guarded worker integration."""
import hashlib,io,json,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
D=Path(__file__).resolve().parent
STOCK_SHA='feef8a8dc3a27395e47232c2b25a5da7a7ab335922fbb527e637c439e35bcec7'
ORIGINAL_SHA='c8b5407c615b60c05078bc7ba9ada8cf53c905bac17faa59561f948feac0d430'
HIGH_SHA='4eb555dc16ad54bdcfecd244b63bfea7ee691ce67b8274a1244644392ba15e13'
PROFILES={'low':[1.5,1.5,1.5],'medium':[2.5,2,1.5],'high':[3,3,2]}
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(v,message):
 if not v:raise ValueError(message)
def build(folder,stock,compiler):
 raw=stock.read_bytes();require(sha(raw)==STOCK_SHA,'unknown stock libaaa')
 elf=ELFFile(io.BytesIO(raw))
 seg=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=0xac380 and 0xac7ac<=s['p_vaddr']+s['p_filesz'])
 at=seg['p_offset']+0xac380-seg['p_vaddr'];original=raw[at:at+1068]
 require(sha(original)==ORIGINAL_SHA,'unknown stock speed function')
 require((folder/'speed-original').read_bytes()==original,'original bundle drift')
 require(sha((folder/'speed-candidate').read_bytes())==HIGH_SHA,'unknown High baseline')
 template=(D/'speed-levels.S').read_text()
 records={}
 for name,multipliers in PROFILES.items():
  path=folder/('speed-candidate' if name=='high' else 'speed-candidate-'+name)
  if name!='high':
   source=folder/('speed-'+name+'.S');obj=folder/('speed-'+name+'.o')
   source.write_text(template.replace('__TYPE0__',str(float(multipliers[0]))).replace('__TYPE1__',str(float(multipliers[1]))).replace('__TYPE2__',str(float(multipliers[2]))))
   subprocess.run([compiler,'--target=aarch64-linux-gnu','-c',str(source),'-o',str(obj)],check=True)
   e=ELFFile(io.BytesIO(obj.read_bytes()));require(not any(s['sh_type']=='SHT_RELA' and s.num_relocations() for s in e.iter_sections()),'unresolved speed relocations')
   text=e.get_section_by_name('.text').data();require(len(text)==0x1a0,'speed assembly drift')
   candidate=bytearray(original)
   candidate[0xac6c4-0xac380:0xac6c8-0xac380]=text[0xdc:0xe0]
   candidate[0xac724-0xac380:0xac788-0xac380]=text[0x13c:0x1a0]
   path.write_bytes(candidate)
  records[name]={'multipliers':multipliers,'source':path.name,'sha256':sha(path.read_bytes())}
 return dict(format=1,default='medium',levels=records,storage='app-owned-persistent-choice',stockFunctionSha256=ORIGINAL_SHA,preBoostCeiling=21844)
def upgrade_worker(text,spec):
 """Apply explicit deltas to the original stable worker, preserving its policies."""
 def change(before,after):
  nonlocal text
  require(text.count(before)==1,'speed worker anchor drift: '+before[:70]);text=text.replace(before,after,1)
 hashes=spec['levels'];policy=(D/'speed-level-policy.sh').read_text().replace('__LOW_HASH__',hashes['low']['sha256']).replace('__MEDIUM_HASH__',hashes['medium']['sha256'])
 change(' enable) [ "$((FEATURE_MASK & 2))" != 0 ] || exit 38;;',' enable|speed_low|speed_medium|speed_high) [ "$((FEATURE_MASK & 2))" != 0 ] || exit 38;;')
 change('CANDIDATE='+HIGH_SHA,policy.rstrip())
 change('if [ "$CURRENT" = "$CANDIDATE" ]; then','if speed_known "$CURRENT"; then')
 change('[ "$CURRENT" != "$CANDIDATE" ] || active=true','if speed_known "$CURRENT"; then active=true; fi')
 change('if [ "$CURRENT" != "$ORIGINAL" ] && [ "$CURRENT" != "$CANDIDATE" ]; then','if [ "$CURRENT" != "$ORIGINAL" ] && ! speed_known "$CURRENT"; then')
 change('[ "$CURRENT" != "$CANDIDATE" ] || {','[ "$CURRENT" = "$ORIGINAL" ] || {\n  speed_known "$CURRENT" && [ "$(file_sha "$D/candidate")" = "$CURRENT" ] || return 1')
 # Extract the reviewed installer as a shared function for enable and switching.
 begin=text.index('  if [ "$CURRENT" = "$ORIGINAL" ]; then\n',text.index(' enable)\n'))
 end=text.index('  : >"$ENABLED"; active=true;;',begin)
 body=text[begin:end].replace('cp "$BASE/candidate" "$D/candidate"','[ "$(file_sha "$SPEED_FILE")" = "$CANDIDATE" ]\n   cp "$SPEED_FILE" "$D/candidate"')
 guarded=[];in_heredoc=False
 for line in body.splitlines():
  token=line.strip()
  if in_heredoc:
   guarded.append(line)
   if token=='RESTORE':in_heredoc=False
  elif "<<'RESTORE'" in line:
   guarded.append(line+' || return 1');in_heredoc=True
  elif token and not token.startswith(('#','if ','for ','case ','fi','done')):
   guarded.append(line+' || return 1')
  else:guarded.append(line)
 body='\n'.join(guarded)+'\n'
 function='speed_install() {\n [ "$CURRENT" = "$ORIGINAL" ] || [ "$CURRENT" = "$CANDIDATE" ] || return 1\n'+body+'  active=true\n}\n'
 text=text[:begin]+'  if [ "$active" = true ] && [ "$CURRENT" != "$CANDIDATE" ]; then restore; fi\n  speed_install\n'+text[end:]
 change('case "$action" in\n master_on)',function+'case "$action" in\n master_on)')
 change(' status) ;;',' speed_low|speed_medium|speed_high) speed_select;;\n status) ;;')
 change('  restore\n  if [ "$afc" = true ]; then','  rm -f "$ENABLED"; sync\n  restore\n  if [ "$action" = restore_all ]; then rm -f "$LEVEL" "$LEVEL.next"; speedLevel=medium; speed_config "$speedLevel"; fi\n  if [ "$afc" = true ]; then')
 change(' master_off)\n',' master_off|restore_all)\n')
 change(' disable) restore; rm -f "$ENABLED";;',' disable) rm -f "$ENABLED"; sync; restore;;')
 change("if [ \"$active\" = true ]; then message='对焦加速 buff 已开启：×3 / ×3 / ×2'",'if [ "$active" = true ]; then message="对焦加速已开启：$speedLevel"')
 change('"message":"%s"}', '"speedLevel":"%s","message":"%s"}')
 change('"$FEATURE_MASK" "$message"','"$FEATURE_MASK" "$speedLevel" "$message"')
 return text
