import QtQuick
QtObject {
 id: root
 property bool masterEnabled: false
 property bool followMaster: false
 property bool installed: true
 property bool ready: false
 property bool enabledPreference: false
 property bool availablePreference: false
 property bool effective: false
 property real applied: 1
 property bool pageActive: false
 property bool busy: false
 property bool inFlight: false
 property string state: "connecting"
 property var pending: null
 property int sequence: 0
 property var completion: null
 property Timer deadline: Timer {
  interval: 1500
  onTriggered: {
   root.sequence++;var xhr=root.pending;root.pending=null;root.busy=false;root.inFlight=false;root.ready=false;
   root.state="display_unavailable";if(xhr)xhr.abort();root.finish(false)
  }
 }
 function finish(ok) {var fn=completion;completion=null;if(fn)fn(ok)}
 function request(action, callback) {
  if (!installed) return false
  if (inFlight) {
   // A user command takes precedence over a status read or previous command.
   if(action === "status")return false
   sequence++;if(pending)pending.abort();pending=null;deadline.stop();busy=false;inFlight=false;finish(false)
  }
  completion=callback || null;inFlight=true;busy=action!=="status";var serial=++sequence
  var xhr=new XMLHttpRequest();pending=xhr
  xhr.onreadystatechange=function(){
   if(xhr.readyState!==XMLHttpRequest.DONE||serial!==sequence)return
   deadline.stop();pending=null;busy=false;inFlight=false;var ok=false
   try {
    var reply=JSON.parse(xhr.responseText);ok=xhr.status===200&&reply.ok===true
    ready=ok&&reply.ready===true;state=reply.state||"display_unavailable"
    if(ok){if(followMaster)masterEnabled=reply.master===true;enabledPreference=reply.enabled===true;availablePreference=reply.available===true;
     effective=reply.effective===true;applied=Number(reply.applied)||1}
   }catch(error){ready=false;state="display_unavailable"}
   finish(ok)
  }
  xhr.open(action==="status"?"GET":"POST","http://127.0.0.1:18765/display/"+action)
  deadline.restart();xhr.send();return true
 }
 function toggle(){
  if(!masterEnabled||!availablePreference||(!ready&&!enabledPreference))return false
  var wasEnabled=enabledPreference
  return request(wasEnabled?"disable":"enable")
 }
 function toggleFeature(){
  if(!masterEnabled||(!ready&&!availablePreference))return false
  return request(availablePreference?"feature-disable":"feature-enable")
 }
 property Timer poll: Timer {interval: root.pageActive ? 200 : 1000; running: root.installed; repeat: true; onTriggered: root.request("status")}
 onInstalledChanged: if (installed) request("status")
 Component.onCompleted: request("status")
 Component.onDestruction:{sequence++;if(pending)pending.abort()}
}
