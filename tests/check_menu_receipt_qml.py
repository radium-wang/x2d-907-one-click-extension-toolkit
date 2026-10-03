"""Execute the actual Bootstrap receipt function in Qt's JS engine; no camera."""
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
app=QCoreApplication([]);engine=QJSEngine()
text=(Path(__file__).resolve().parents[1]/'src/Bootstrap.qml').read_text()
start=text.index('    function reportMenuState()')
end=text.index('    Timer {',start)
fn=text[start:end]
script='''var attached=true,playButton={},prankButton=null,grid={count:12};
var adapter={extensionPresent:true,prankPresent:false};
var reportedMenuState="",menuReportTick=0,marker="",requests=0;
var root=this;
function XMLHttpRequest(){this.status=200;this.readyState=4;this.responseText='{"menuAcknowledged":true}';}
XMLHttpRequest.DONE=4;
XMLHttpRequest.prototype.open=function(method,url){this.url=url};
XMLHttpRequest.prototype.send=function(){requests++;marker=this.url.split('/').pop();this.onreadystatechange()};
'''+fn+'''
function check(condition,message){if(!condition)throw new Error(message)}
reportMenuState();check(marker==="menu_ready_12","initial receipt");
marker="";
for(var i=0;i<5;i++)reportMenuState();
check(marker==="menu_ready_12","service restart must regain receipt without menu changes");
check(requests===2,"periodic refresh should be bounded");
playButton=null;reportMenuState();check(marker==="menu_unavailable","missing menu must revoke receipt");
adapter.prankPresent=true;playButton={};prankButton=null;reportMenuState();
check(marker==="menu_unavailable","joke button must exist too");
prankButton={};reportMenuState();check(marker==="menu_ready_12","both buttons verified");
attached=false;marker="";for(var j=0;j<10;j++)reportMenuState();check(marker==="","detached menu cannot acknowledge");
true;
'''
result=engine.evaluate(script)
assert not result.isError(),result.toString()
assert result.toBool()
print('Actual Qt menu receipt refresh, service restart and revocation passed')
