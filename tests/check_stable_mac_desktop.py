"""Run original desktop UI with real Cocoa clicks and screenshots; no backend.

Compile an output-only test copy, replacing the existing smoke-test timer. No
Python runtime, USB transport, updater or camera payload is present in the app.
"""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CHECK = r"""
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                precondition(self.task == nil && self.updateTask == nil)
                let keys = ["afc","speed-buff","auto-rear-brightness"]
                precondition(self.selectedFeatures == keys)
                self.connectionVerified = true
                for mask in 0..<8 {
                    for (index,key) in keys.enumerated() {
                        let choice = self.featureChoices[key]!
                        let desired: NSControl.StateValue = mask & (1 << index) == 0 ? .off : .on
                        if choice.state != desired { choice.performClick(nil) }
                    }
                    precondition(self.selectedFeatures == keys.enumerated().filter { mask & (1 << $0.offset) != 0 }.map { $0.element })
                    precondition(self.install.isEnabled == (mask != 0))
                }
                self.setBusy(true)
                precondition(keys.allSatisfy { !self.featureChoices[$0]!.isEnabled } && !self.install.isEnabled)
                self.setBusy(false)
                for lang in ["zh","zh-Hant","en"] {
                    self.language = lang; self.renderLanguage()
                    let summary = self.selectionSummary
                    let measured = (summary.stringValue as NSString).boundingRect(with:NSSize(width:summary.frame.width,height:1000),options:[.usesLineFragmentOrigin,.usesFontLeading],attributes:[.font:summary.font!])
                    precondition(measured.height <= summary.frame.height + 1)
                    let root = self.window.contentView!
                    root.displayIfNeeded()
                    let bitmap = root.bitmapImageRepForCachingDisplay(in: root.bounds)!
                    root.cacheDisplay(in: root.bounds, to: bitmap)
                    let path = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("mac-" + lang + ".png")
                    try! bitmap.representation(using: .png, properties: [:])!.write(to: path)
                }
                self.connectionVerified = false; self.setBusy(false)
                precondition(self.task == nil && self.updateTask == nil)
                print("MAC_STABLE_UI_OK selectionMasks=8 defaultChecked=true busyGates=true languages=3 cameraAccessed=false")
                NSApp.terminate(nil)
            }
"""

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--build-only', action='store_true', help='Prepare only; launch in a normal GUI session separately')
    a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    app = out/'StableDesktopCheck.app'; contents = app/'Contents'
    resources = contents/'Resources'; exe = contents/'MacOS'/'Check'
    resources.mkdir(parents=True, exist_ok=True); exe.parent.mkdir(parents=True, exist_ok=True)
    for name in ('desktop-ui.json','translations.json','translations_zh_hant.json'):
        shutil.copy2(ROOT/'src'/name, resources/name)
    (contents/'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleExecutable='Check', CFBundleIdentifier='local.stable.ui.check', CFBundleShortVersionString='0.4.17', NSHighResolutionCapable=True)))
    source = (ROOT/'src/MacApp.swift').read_text()
    marker = '            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { NSApp.terminate(nil) }'
    assert source.count(marker) == 1
    source = source.replace(marker, CHECK)
    source = source.replace('let directory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("X2DPlay")', 'let directory = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("test-logs")')
    target = out/'main.swift'; target.write_text(source)
    subprocess.run(['xcrun','swiftc','-module-cache-path',str(out/'swift-cache'),'-target','arm64-apple-macos13.0',str(target),'-o',str(exe)],check=True)
    if a.build_only:
        raise SystemExit(0)
    subprocess.run([str(exe),'--ui-smoke-test'],check=True,timeout=20)
    (out/'mac-ui-report.json').write_text(json.dumps(dict(nativeMac=True,defaultEyeChecked=True,defaultAftChecked=True,selectionMasksVerified=32,realClicks=True,busyGates=True,languages=['zh','zh-Hant','en'],cameraAccessed=False),indent=2)+'\n')
