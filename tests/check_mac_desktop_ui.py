"""Native AppKit layout/selection checks in an isolated smoke-test bundle.

The built app uses the repository's Swift views and resources. Only its existing
smoke-test branch is replaced with assertions and image export; no USB or update
worker runs, and user preferences are never written.
"""
import argparse
import json
import os
import platform
import plistlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = r'''
            DispatchQueue.main.async {
                let output = ProcessInfo.processInfo.environment["X2D_UI_CHECK_OUTPUT"]!
                let height = ProcessInfo.processInfo.environment["X2D_UI_CHECK_HEIGHT"]!
                let expected = ["afc", "speed-buff", "auto-rear-brightness"]
                precondition(self.selectedFeatures == expected)
                func receiveStatus(_ values: [String: Any]) {
                    let data = try! JSONSerialization.data(withJSONObject: values)
                    self.currentAction = "status"
                    self.consume("X2D_EVENT " + String(decoding: data, as: UTF8.self))
                    self.setBusy(false)
                }
                var status907: [String: Any] = ["type":"status", "connected":true, "firmware":"4.2.0", "model":"907X & CFV 100C", "installed":false, "message":"相机就绪，原厂状态"]
                receiveStatus(status907)
                precondition(!self.prankCheckbox.isHidden && self.prankCheckbox.isEnabled && self.prankCheckbox.state == .on)
                if height == "840" {
                    self.language = "zh"; self.renderLanguage()
                    let canvas = self.mainCanvas!
                    canvas.layoutSubtreeIfNeeded()
                    let image = canvas.bitmapImageRepForCachingDisplay(in: canvas.bounds)!
                    canvas.cacheDisplay(in: canvas.bounds, to: image)
                    let path = URL(fileURLWithPath: output).appendingPathComponent("mac-zh-907.png")
                    try! image.representation(using: .png, properties: [:])!.write(to: path)
                }
                self.run("install")  // The private test build intercepts arguments before process launch.
                self.prankCheckbox.state = .off
                for busy in [true, false] { self.setBusy(busy); precondition(self.prankCheckbox.state == .off) }
                self.renderLanguage(); precondition(self.prankCheckbox.state == .off)
                self.run("install")
                status907["installed"] = true; status907["verifiedPrankIbis"] = true
                status907["state"] = ["ready":false, "prankIbis":false]
                receiveStatus(status907); precondition(self.prankCheckbox.state == .on)
                self.run("install")
                self.run("status"); precondition(self.prankCheckbox.isHidden && self.prankCheckbox.state == .off)
                receiveStatus(status907); precondition(self.prankCheckbox.state == .on)
                self.consume("X2D_EVENT {\"type\":\"error\"}")
                precondition(self.prankCheckbox.state == .off && !self.connectionVerified)
                status907["verifiedPrankIbis"] = false
                receiveStatus(status907); precondition(self.prankCheckbox.state == .off)
                self.run("install")
                status907["verifiedPrankIbis"] = 1
                receiveStatus(status907); precondition(self.prankCheckbox.state == .off)
                status907.removeValue(forKey: "verifiedPrankIbis"); status907["recovery"] = true
                receiveStatus(status907); precondition(self.prankCheckbox.state == .off)
                status907["model"] = "X2D 100C"; status907["verifiedPrankIbis"] = true
                receiveStatus(status907); precondition(self.prankCheckbox.isHidden && self.prankCheckbox.state == .off)
                for language in ["zh", "zh-Hant", "en"] {
                    self.language = language
                    self.renderLanguage()
                    self.featureChoices["eye-detection"]!.state = .on
                    self.connectionVerified = true
                    for busy in [false, true, false] {
                        self.setBusy(busy)
                        precondition(self.selectedFeatures == expected + ["eye-detection"])
                        for key in ["pixelshift", "facetracking"] {
                            let choice = self.featureChoices[key]!
                            precondition(!choice.isEnabled && choice.state == .off)
                            choice.performClick(nil)
                            precondition(choice.state == .off)
                        }
                    }
                    precondition(self.install.isEnabled)
                    precondition(self.featureCount.stringValue.contains("4"))
                    for key in ["eye", "eyedescription", "pixelshift", "pixelshiftdescription", "facetracking", "facetrackingdescription"] {
                        let field = self.desktopFields[key]!
                        precondition(!field.stringValue.isEmpty)
                        precondition(field.cell!.cellSize(forBounds: field.bounds).height <= field.bounds.height + 1)
                    }
                    let viewport = self.window.contentView as! NSScrollView
                    self.window.makeFirstResponder(self.install)
                    precondition(viewport.documentVisibleRect.contains(self.install.frame))
                    let canvas = self.mainCanvas!
                    canvas.layoutSubtreeIfNeeded()
                    let image = canvas.bitmapImageRepForCachingDisplay(in: canvas.bounds)!
                    canvas.cacheDisplay(in: canvas.bounds, to: image)
                    let path = URL(fileURLWithPath: output).appendingPathComponent("mac-" + language + "-" + height + ".png")
                    try! image.representation(using: .png, properties: [:])!.write(to: path)
                    let visibleImage = viewport.bitmapImageRepForCachingDisplay(in: viewport.bounds)!
                    viewport.cacheDisplay(in: viewport.bounds, to: visibleImage)
                    let visiblePath = URL(fileURLWithPath: output).appendingPathComponent("mac-" + language + "-viewport-" + height + ".png")
                    try! visibleImage.representation(using: .png, properties: [:])!.write(to: visiblePath)
                    self.featureChoices["eye-detection"]!.state = .off
                }
                print("Native AppKit: 3 languages, 4 selections, disabled placeholders, focus scrolling passed at " + height)
                NSApp.terminate(nil)
            }
'''


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    app = output / 'DesktopCardsCheck.app'
    resources = app / 'Contents/Resources'
    executable = app / 'Contents/MacOS/X2DPlay'
    resources.mkdir(parents=True, exist_ok=True)
    executable.parent.mkdir(parents=True, exist_ok=True)
    for name in ('desktop-ui.json', 'translations.json', 'translations_zh_hant.json'):
        shutil.copy2(ROOT / 'src' / name, resources / name)
    (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(dict(
        CFBundleIdentifier='local.x2d.desktop-cards-check', CFBundleExecutable='X2DPlay',
        CFBundleName='Desktop cards check', CFBundlePackageType='APPL',
        # Current source version; this remains an isolated offline UI check.
        CFBundleShortVersionString='0.4.15', NSHighResolutionCapable=True)))
    source = (ROOT / 'src/MacApp.swift').read_text()
    marker = '            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { NSApp.terminate(nil) }'
    assert source.count(marker) == 1
    source = source.replace(marker, CHECK)
    before_launch='        var environment = ProcessInfo.processInfo.environment'
    assert source.count(before_launch) == 1
    source = source.replace(before_launch, r'''
        if CommandLine.arguments.contains("--ui-smoke-test") {
            precondition(worker.arguments!.contains("--prank-ibis") == (detectedModel == "907X & CFV 100C" && prankCheckbox.state == .on))
            try? confirmationInput?.close(); confirmationInput = nil
            setBusy(false)
            return
        }
''' + before_launch)
    height = '        let viewportHeight = min(look.height, availableHeight)'
    assert source.count(height) == 1
    source = source.replace(height, '        let viewportHeight = min(look.height, Double(ProcessInfo.processInfo.environment["X2D_UI_CHECK_HEIGHT"]!)!)')
    source = source.replace('        let availableHeight = max(320, (NSScreen.main?.visibleFrame.height ?? look.height+80)-80)\n', '')
    swift = output / 'DesktopCardsCheck.swift'
    swift.write_text(source)
    subprocess.run(['swiftc', '-O', '-module-cache-path', str(output / 'swift-cache'),
                    '-target', platform.machine() + '-apple-macosx13.0', str(swift), '-o', str(executable)], check=True)
    for height in ('840', '560'):
        environment = dict(os.environ, X2D_UI_CHECK_HEIGHT=height, X2D_UI_CHECK_OUTPUT=str(output.resolve()))
        subprocess.run([str(executable), '--ui-smoke-test'], env=environment, check=True, timeout=30)
    report = dict(nativeAppKit=True, cameraTested=False, languages=['zh', 'zh-Hant', 'en'],
                  viewportHeights=[840, 560], selectableFeatures=4, disabledPlaceholders=2,
                  verified907Choice=True, stock907Default=True, manualCancelPreserved=True, installPrankArguments=True)
    (output / 'native-ui-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
