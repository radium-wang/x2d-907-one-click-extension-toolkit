import Cocoa

struct DesktopLook: Decodable {
    let width: Double
    let height: Double
    let colors: [String: String]
    let layout: [String: [Double]]
    let languageLayout: [String: [String: [Double]]]?
    static let shared: DesktopLook = {
        let url = Bundle.main.resourceURL!.appendingPathComponent("desktop-ui.json")
        return try! JSONDecoder().decode(DesktopLook.self, from: Data(contentsOf: url))
    }()
    func rect(_ key: String, language: String = "zh") -> NSRect {
        let v = languageLayout?[language]?[key] ?? layout[key]!
        return NSRect(x: v[0], y: v[1], width: v[2], height: v[3])
    }
    func color(_ key: String) -> NSColor {
        let rgb = UInt32(colors[key]!.dropFirst(), radix: 16)!
        return NSColor(srgbRed: CGFloat((rgb >> 16) & 255)/255, green: CGFloat((rgb >> 8) & 255)/255, blue: CGFloat(rgb & 255)/255, alpha: 1)
    }
}
final class ToolkitButton: NSButton {
    var primary = false
    var checkbox = false
    var checkboxInset: CGFloat = 0
    override var isFlipped: Bool { true }
    override func draw(_ dirtyRect: NSRect) {
        let look = DesktopLook.shared
        let alpha: CGFloat = isEnabled ? 1 : 0.48
        let rect = checkbox ? NSRect(x: checkboxInset, y: (bounds.height-18)/2, width: 18, height: 18) : bounds.insetBy(dx: 0.5, dy: 0.5)
        let path = NSBezierPath(roundedRect: rect, xRadius: checkbox ? 4 : 7, yRadius: checkbox ? 4 : 7)
        let selected = checkbox ? state == .on : primary
        (selected ? look.color("blue") : look.color("background")).withAlphaComponent(alpha).setFill(); path.fill()
        (selected ? look.color("blue") : NSColor(srgbRed: 216/255, green: 216/255, blue: 220/255, alpha: 1)).withAlphaComponent(alpha).setStroke(); path.lineWidth = 1; path.stroke()
        if checkbox {
            if selected {
                NSColor.white.withAlphaComponent(alpha).setStroke()
                let check = NSBezierPath(); check.move(to: NSPoint(x: checkboxInset+4, y: bounds.midY)); check.line(to: NSPoint(x: checkboxInset+7, y: bounds.midY+3)); check.line(to: NSPoint(x: checkboxInset+13, y: bounds.midY-4)); check.lineWidth = 2; check.stroke()
            }
            if !title.isEmpty {
                let text = NSAttributedString(string: title, attributes: [.font: NSFont.systemFont(ofSize: 14), .foregroundColor: look.color("text")])
                text.draw(at: NSPoint(x: checkboxInset+27, y: (bounds.height-text.size().height)/2))
            }
        } else {
            let style = NSMutableParagraphStyle(); style.alignment = .center
            let attributes: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 13, weight: .medium), .foregroundColor: (selected ? NSColor.white : look.color("text")).withAlphaComponent(alpha), .paragraphStyle: style]
            let text = NSAttributedString(string: title, attributes: attributes)
            text.draw(in: NSRect(x: 8, y: (bounds.height-text.size().height)/2, width: bounds.width-16, height: text.size().height))
        }
        if window?.firstResponder === self {
            look.color("blue").setStroke()
            let ring = NSBezierPath(roundedRect: checkbox ? rect.insetBy(dx: -2,dy: -2) : bounds.insetBy(dx: 1, dy: 1), xRadius: 7, yRadius: 7); ring.lineWidth = 2; ring.stroke()
        }
    }
}
final class ToolkitProgress: NSProgressIndicator {
    override func draw(_ dirtyRect: NSRect) {
        let look = DesktopLook.shared
        look.color("surface").setFill(); NSBezierPath(roundedRect: bounds, xRadius: 3, yRadius: 3).fill()
        if doubleValue > 0 {
            look.color("blue").setFill(); NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: bounds.width*doubleValue/100, height: bounds.height), xRadius: 3, yRadius: 3).fill()
        }
    }
}
final class ToolkitLanguagePicker: NSPopUpButton {
    override var isFlipped: Bool { true }
    override func draw(_ dirtyRect: NSRect) {
        let look = DesktopLook.shared
        let shape = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5), xRadius: 8, yRadius: 8)
        look.color("background").setFill(); shape.fill(); look.color("border").setStroke(); shape.stroke()
        let text = NSAttributedString(string: selectedItem?.title ?? "", attributes: [.font: NSFont.systemFont(ofSize: 14), .foregroundColor: look.color("text")])
        text.draw(at: NSPoint(x: 11, y: (bounds.height-text.size().height)/2))
        look.color("secondary").setStroke()
        let arrow = NSBezierPath(); arrow.move(to: NSPoint(x: bounds.width-23, y: bounds.midY-2)); arrow.line(to: NSPoint(x: bounds.width-18, y: bounds.midY+3)); arrow.line(to: NSPoint(x: bounds.width-13, y: bounds.midY-2)); arrow.lineWidth=1.3; arrow.stroke()
    }
}
final class ToolkitCanvas: NSView {
    var mainSurface = true
    var language = "zh"
    var verified = false
    var busy = false
    override var isFlipped: Bool { true }
    override func draw(_ dirtyRect: NSRect) {
        let look = DesktopLook.shared
        look.color("background").setFill(); bounds.fill()
        if !mainSurface { return }
        for (key,radius,fill,border) in [("logbox",9.0,"background",true),("box",10.0,"background",true),("summarybox",8.0,"surface",false)] {
            let shape = NSBezierPath(roundedRect: look.rect(key).insetBy(dx: 0.5, dy: 0.5), xRadius: radius, yRadius: radius)
            look.color(fill).setFill(); shape.fill()
            if border { look.color("border").setStroke(); shape.lineWidth = 1; shape.stroke() }
        }
        look.color("border").setStroke()
        for (x,y,w) in [(392.0,198.0,560.0),(392.0,288.0,560.0),(43.0,140.0,310.0),(43.0,546.0,310.0)] {
            let line = NSBezierPath(); line.move(to: NSPoint(x: x, y: y)); line.line(to: NSPoint(x: x+w, y: y)); line.lineWidth = 1; line.stroke()
        }
        look.color(busy ? "blue" : verified ? "green" : "orange").setFill(); NSBezierPath(ovalIn: NSRect(x: look.rect("state",language: language).minX-13, y: 434, width: 8, height: 8)).fill()
        for (kind,y) in [("focus",153.0),("bolt",233.0),("sun",314.0)] {
            let x=448.0
            let lines: [[NSPoint]]
            if kind == "focus" { lines = [[NSPoint(x:0,y:5),NSPoint(x:0,y:1),NSPoint(x:1,y:0),NSPoint(x:5,y:0)],[NSPoint(x:13,y:0),NSPoint(x:17,y:0),NSPoint(x:18,y:1),NSPoint(x:18,y:5)],[NSPoint(x:18,y:13),NSPoint(x:18,y:17),NSPoint(x:17,y:18),NSPoint(x:13,y:18)],[NSPoint(x:5,y:18),NSPoint(x:1,y:18),NSPoint(x:0,y:17),NSPoint(x:0,y:13)]] }
            else if kind == "bolt" { lines = [[NSPoint(x:10,y:0),NSPoint(x:3,y:10),NSPoint(x:9,y:10),NSPoint(x:7,y:18),NSPoint(x:15,y:7),NSPoint(x:9,y:7),NSPoint(x:10,y:0)]] }
            else { lines = (0..<8).map { i in let angle=Double(i)*Double.pi/4; return [NSPoint(x:9+6.5*cos(angle),y:9+6.5*sin(angle)),NSPoint(x:9+9*cos(angle),y:9+9*sin(angle))] } }
            look.color("secondary").setStroke()
            for points in lines { let line=NSBezierPath(); line.move(to: NSPoint(x:x+points[0].x,y:y+points[0].y)); for p in points.dropFirst() {line.line(to: NSPoint(x:x+p.x,y:y+p.y))};line.lineWidth=1.3;line.stroke() }
            if kind == "sun" { NSBezierPath(ovalIn:NSRect(x:x+5,y:y+5,width:8,height:8)).stroke() }
        }
    }
}


final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    let status = NSTextField(labelWithString: "等待连接检查")
    let detail = NSTextField(wrappingLabelWithString: "连接相机并开机，点击“已连接”检查状态。907X 100C 适配版待实机验证。")
    let progress = ToolkitProgress()
    let install = ToolkitButton(title: "安装所选功能", target: nil, action: nil)
    var featureChoices: [String: NSButton] = [:]
    let featureCount = NSTextField(labelWithString: "")
    let logState = NSTextField(labelWithString: "")
    let selectionSummary = NSTextField(wrappingLabelWithString: "")
    var selectedFeatures: [String] {
        ["afc", "speed-buff", "auto-rear-brightness"].filter { featureChoices[$0]?.state == .on }
    }
    let restore = ToolkitButton(title: "一键恢复原状", target: nil, action: nil)
    let refresh = ToolkitButton(title: "已连接", target: nil, action: nil)
    let logs = NSTextView()
    let prankCheckbox = NSButton(checkboxWithTitle: "添加防抖功能（907 彩蛋）", target: nil, action: nil)
    var detectedModel = ""
    var task: Process?
    var confirmationInput: FileHandle?
    var installLanguage = "zh"
    var logBuffer = ""
    var language: String = {
        let saved = UserDefaults.standard.string(forKey: "AppLanguage") ?? "zh"
        return ["zh", "zh-Hant", "en"].contains(saved) ? saved : "zh"
    }()
    var translations: [String: String] = [:]
    var traditionalTranslations: [String: String] = [:]
    var fragments: [String] = []
    var traditionalFragments: [String] = []
    var desktopFields: [String: NSTextField] = [:]
    var localizedImages: [(NSImageView, String)] = []
    var localizedFields: [ObjectIdentifier: (NSTextField, String)] = [:]
    let languageChoice = ToolkitLanguagePicker(frame: .zero, pullsDown: false)
    let settingsButton = ToolkitButton(title: "设置", target: nil, action: nil)
    let settingsCloseButton = ToolkitButton(title: "关闭", target: nil, action: nil)
    var settingsWindow: NSWindow?
    let automaticUpdates = ToolkitButton(title: "启动时自动检查更新", target: nil, action: nil)
    let downloadUpdateButton = ToolkitButton(title: "下载并安装更新", target: nil, action: nil)
    let settingsUpdateStatus = NSTextField(wrappingLabelWithString: "自动检查只查找新版，不会自动下载或安装。")
    var autoCheckUpdates = UserDefaults.standard.object(forKey: "AutoCheckUpdates") == nil
        ? true : UserDefaults.standard.bool(forKey: "AutoCheckUpdates")
    var quitItem: NSMenuItem!
    var appVersion = ""
    let updateButton = ToolkitButton(title: "检查更新", target: nil, action: nil)
    var updateVersion = ""
    var updateBusy = false
    var updateRestarting = false
    var updateTask: Process?

    func translated(_ text: String) -> String {
        if language == "zh" { return text.replacingOccurrences(of: "Windows", with: "系统") }
        let catalog = language == "zh-Hant" ? traditionalTranslations : translations
        let keys = language == "zh-Hant" ? traditionalFragments : fragments
        var value = catalog[text] ?? text
        if catalog[text] == nil {
            for key in keys where value.contains(key) {
                value = value.replacingOccurrences(of: key, with: catalog[key]!)
            }
        }
        return value.replacingOccurrences(of: "Windows", with: language == "zh-Hant" ? "系統" : "the system")
    }
    func setLocalized(_ field: NSTextField, _ text: String) {
        localizedFields[ObjectIdentifier(field)] = (field, text)
        field.stringValue = translated(text)
    }
    func localize(_ field: NSTextField) { setLocalized(field, field.stringValue) }
    func renderLog() {
        let text = logBuffer.components(separatedBy: "\n").map { translated($0) }.joined(separator: "\n")
        logs.string = String(text.suffix(14000))
        logs.scrollToEndOfDocument(nil)
        if let file = logFile { try? text.write(to: file, atomically: true, encoding: .utf8) }
    }
    func renderLanguage() {
        let look = DesktopLook.shared
        for (key,field) in desktopFields { field.frame = look.rect(key,language: language) }
        for (field,key) in [(featureCount,"featurecount"),(logState,"logstate"),(selectionSummary,"selectionsummary"),(status,"state")] { field.frame = look.rect(key,language: language) }
        for (button,key) in [(refresh,"statusbutton"),(install,"installbutton"),(restore,"restorebutton")] { button.frame = look.rect(key,language: language) }
        for (field, source) in localizedFields.values { field.stringValue = translated(source) }
        for (image, source) in localizedImages { image.setAccessibilityLabel(translated(source)) }
        prankCheckbox.title = translated("添加防抖功能（907 彩蛋）")
        updateButton.title = translated("检查更新")
        downloadUpdateButton.title = translated("下载并安装更新")
        settingsButton.title = translated("设置")
        settingsWindow?.title = translated("设置")
        settingsCloseButton.title = translated("关闭")
        automaticUpdates.title = translated("启动时自动检查更新")
        refresh.title = translated("已连接")
        install.title = translated("安装所选功能")
        restore.title = translated("恢复原状")
        quitItem.title = translated("退出 x2d/907一键扩展功能-工具包")
        window.title = translated("x2d/907 扩展功能工具包") + " · " + appVersion
        languageChoice.selectItem(at: language == "zh-Hant" ? 1 : language == "en" ? 2 : 0)
        updateButton.frame.size.width = language == "en" ? 134 : 82
        downloadUpdateButton.frame.origin.x = 24 + updateButton.frame.width + 10
        downloadUpdateButton.frame.size.width = language == "en" ? 238 : 134
        renderLog()
        setBusy(task != nil)
    }
    @objc func languageChanged() {
        language = languageChoice.indexOfSelectedItem == 1 ? "zh-Hant" : languageChoice.indexOfSelectedItem == 2 ? "en" : "zh"
        UserDefaults.standard.set(language, forKey: "AppLanguage")
        renderLanguage()
    }
    @objc func automaticUpdatesChanged() {
        autoCheckUpdates = automaticUpdates.state == .on
        UserDefaults.standard.set(autoCheckUpdates, forKey: "AutoCheckUpdates")
    }
    @objc func settingsClosed() { settingsWindow?.orderOut(nil) }
    @objc func settingsClicked() {
        guard task == nil, !updateBusy else { return }
        if settingsWindow == nil {
            let panel = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 450, height: 284), styleMask: [.titled, .closable], backing: .buffered, defer: false)
            panel.isReleasedWhenClosed = false; panel.appearance = NSAppearance(named: .aqua); settingsWindow = panel
            let root = ToolkitCanvas(frame: NSRect(x: 0,y: 0,width: 450,height: 284)); root.mainSurface = false; panel.contentView = root
            func label(_ text: String, _ rect: NSRect, _ size: CGFloat, _ bold: Bool = false) {
                let field = NSTextField(labelWithString: text); localize(field); field.frame = rect; field.font = .systemFont(ofSize: size, weight: bold ? .semibold : .regular); field.textColor = DesktopLook.shared.color("text"); root.addSubview(field)
            }
            label("设置", NSRect(x: 24,y: 28,width: 160,height: 23),16,true)
            label("语言", NSRect(x: 24,y: 85,width: 100,height: 22),14)
            settingsCloseButton.frame = NSRect(x: 370,y: 24,width: 56,height: 36); settingsCloseButton.isBordered = false; settingsCloseButton.target = self; settingsCloseButton.action = #selector(settingsClosed); root.addSubview(settingsCloseButton)
            languageChoice.frame = NSRect(x: 278,y: 78,width: 148,height: 36); languageChoice.isBordered = false; root.addSubview(languageChoice)
            automaticUpdates.setButtonType(.switch); automaticUpdates.checkbox = true; automaticUpdates.isBordered = false
            automaticUpdates.frame = NSRect(x: 24,y: 132,width: 402,height: 22); automaticUpdates.state = autoCheckUpdates ? .on : .off
            automaticUpdates.target = self; automaticUpdates.action = #selector(automaticUpdatesChanged); root.addSubview(automaticUpdates)
            localize(settingsUpdateStatus); settingsUpdateStatus.frame = NSRect(x: 24,y: 170,width: 402,height: 36); settingsUpdateStatus.font = .systemFont(ofSize: 12); settingsUpdateStatus.textColor = DesktopLook.shared.color("secondary"); root.addSubview(settingsUpdateStatus)
            for (button,rect,action) in [(updateButton,NSRect(x: 24,y: 224,width: 112,height: 36),#selector(updateClicked)),(downloadUpdateButton,NSRect(x: 148,y: 224,width: 238,height: 36),#selector(downloadUpdateClicked))] {
                button.frame = rect; button.isBordered = false; button.target = self; button.action = action; root.addSubview(button)
            }
            panel.center()
        }
        renderLanguage(); setBusy(false); settingsWindow?.makeKeyAndOrderFront(nil)
    }
    var outputBuffer = ""
    var connectionVerified = false
    var receivedResult = false
    var currentAction = ""
    var pendingUserHint: String?
    var showedRestartHint = false
    var logFile: URL!

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let url = Bundle.main.resourceURL?.appendingPathComponent("translations.json"),
           let data = try? Data(contentsOf: url),
           let catalog = try? JSONDecoder().decode([String: String].self, from: data) {
            translations = catalog
            fragments = catalog.keys.sorted { $0.count == $1.count ? $0 < $1 : $0.count > $1.count }
        }
        if let url = Bundle.main.resourceURL?.appendingPathComponent("translations_zh_hant.json"),
           let data = try? Data(contentsOf: url),
           let catalog = try? JSONDecoder().decode([String: String].self, from: data) {
            traditionalTranslations = catalog
            traditionalFragments = catalog.keys.sorted { $0.count == $1.count ? $0 < $1 : $0.count > $1.count }
        }
        NSApp.setActivationPolicy(.regular)
        let mainMenu = NSMenu()
        let applicationItem = NSMenuItem()
        let applicationMenu = NSMenu()
        quitItem = NSMenuItem(title: "退出 x2d/907一键扩展功能-工具包", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        applicationMenu.addItem(quitItem)
        applicationItem.submenu = applicationMenu
        mainMenu.addItem(applicationItem)
        NSApp.mainMenu = mainMenu
        let look = DesktopLook.shared
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: look.width, height: look.height),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.appearance = NSAppearance(named: .aqua)
        appVersion = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "未知"
        window.delegate = self; window.center()
        let root = ToolkitCanvas(frame: NSRect(x: 0, y: 0, width: look.width, height: look.height))
        window.contentView = root
        func label(_ key: String, _ text: String, _ size: CGFloat = 12, _ weight: NSFont.Weight = .regular, _ color: String = "secondary") {
            let field = NSTextField(wrappingLabelWithString: text)
            localize(field); field.frame = look.rect(key); field.font = .systemFont(ofSize: size, weight: weight)
            field.textColor = look.color(color); root.addSubview(field); desktopFields[key] = field
        }
        label("title", "x2d/907 扩展功能工具包", 21, .semibold, "text")
        label("version", "v" + appVersion)
        label("subtitle", "X2D 100C / 907X 100C · 固件 4.2.0", 13)
        label("logheading", "运行日志", 14, .semibold, "text")
        label("featureheading", "选择要安装的功能", 16, .semibold, "text")
        featureCount.frame = look.rect("featurecount"); featureCount.font = .systemFont(ofSize: 12); featureCount.textColor = look.color("secondary"); root.addSubview(featureCount)
        logState.frame = look.rect("logstate"); logState.font = .systemFont(ofSize: 11); logState.textColor = look.color("secondary"); logState.alignment = .right; root.addSubview(logState)
        label("afc", "AF-C 连续自动对焦", 14, .semibold, "text")
        label("afcdescription", "在相机上开启连续自动对焦。")
        label("buff", "对焦加速", 14, .semibold, "text")
        label("buffdescription", "可选择低、中、高三档加速；可安装，但不建议老镜头用户在相机内开启该功能。", 12, .regular, "orange")
        label("brightness", "后屏自动亮度", 14, .semibold, "text")
        label("brightnessdescription", "根据环境光调节后屏亮度，可设置最高亮度。")
        label("dependency", "三项功能可分别选择。")
        label("summarylabel", "本次安装")
        label("note", "日志保存在本地，便于查看操作进度。", 11)
        for (key,title) in [("afc","AF-C 连续自动对焦"),("speed-buff","对焦加速"),("auto-rear-brightness","后屏自动亮度")] {
            let choice = ToolkitButton(title: "", target: self, action: #selector(featureSelectionChanged))
            choice.setButtonType(.switch); choice.checkbox = true; choice.state = .on; choice.isBordered = false
            let rowTop = key == "afc" ? 127.0 : key == "speed-buff" ? 198.0 : 288.0
            choice.checkboxInset = 16
            choice.frame = NSRect(x: 392,y: rowTop,width: 560,height: key == "speed-buff" ? 90 : 71)
            choice.setAccessibilityLabel(title); featureChoices[key] = choice; root.addSubview(choice)
        }
        for (field,key,size) in [(selectionSummary,"selectionsummary",14.0),(status,"state",12.0),(detail,"detail",12.0)] {
            field.frame = look.rect(key); field.font = .systemFont(ofSize: size); field.textColor = look.color(key == "selectionsummary" ? "text" : "secondary"); root.addSubview(field)
        }
        status.lineBreakMode = .byTruncatingTail
        localize(status); localize(detail)
        prankCheckbox.frame = look.rect("prank"); prankCheckbox.state = .off; prankCheckbox.isHidden = true; root.addSubview(prankCheckbox)
        progress.frame = look.rect("progress"); progress.minValue = 0; progress.maxValue = 100; progress.isIndeterminate = false; progress.style = .bar; progress.controlSize = .small; root.addSubview(progress)
        for (button,key,action) in [(refresh,"statusbutton",#selector(refreshClicked)),(restore,"restorebutton",#selector(restoreClicked)),(install,"installbutton",#selector(installClicked)),(settingsButton,"settingsbutton",#selector(settingsClicked))] {
            button.frame = look.rect(key); button.isBordered = false; button.target = self; button.action = action; root.addSubview(button)
        }
        install.primary = true; refresh.keyEquivalent = "\r"
        languageChoice.addItems(withTitles: ["简体中文", "繁體中文", "English"]); languageChoice.bezelStyle = .rounded
        languageChoice.target = self; languageChoice.action = #selector(languageChanged); languageChoice.setAccessibilityLabel("语言 / Language")
        let scroll = NSScrollView(frame: look.rect("logs")); scroll.hasVerticalScroller = true; scroll.borderType = .noBorder
        logs.isEditable = false; logs.font = .monospacedSystemFont(ofSize: 12, weight: .regular); logs.textColor = look.color("secondary")
        logs.frame = NSRect(origin: .zero, size: scroll.contentSize); logs.autoresizingMask = [.width]; logs.isHorizontallyResizable = false; logs.textContainerInset = .zero
        logs.textContainer?.widthTracksTextView = true; logs.textContainer?.lineFragmentPadding = 0
        let paragraph = NSMutableParagraphStyle(); paragraph.lineSpacing = 7; logs.defaultParagraphStyle = paragraph
        scroll.documentView = logs; root.addSubview(scroll)
        let directory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("X2DPlay")
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        logFile = directory.appendingPathComponent("latest.log")
        renderLanguage()
        window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        if CommandLine.arguments.contains("--ui-smoke-test") {
            setLocalized(status, "等待连接检查")
            appendLog("工具包已启动。")
            appendLog("请将相机开机并连接 USB 数据线。")
            appendLog("连接好后，请点击“已连接”。")
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { NSApp.terminate(nil) }
        } else {
            setBusy(false)
            appendLog("应用版本：" + appVersion)
            appendUpdateNotice()
            appendLog("请将相机开机，并通过 USB 数据线连接 Mac。")
            appendLog("如相机屏幕出现“跳过”按钮，请点击“跳过”，并保持数据线连接。")
            appendLog("连接好后，请点击 App 中的“已连接”；检查通过后即可操作。")
            if autoCheckUpdates {
                DispatchQueue.main.async { self.runUpdate(install: false) }
            }
        }
    }

    @objc func installClicked() { run("install") }
    @objc func restoreClicked() { run("restore") }
    @objc func refreshClicked() { run("status") }
    @objc func featureSelectionChanged() { setBusy(task != nil) }

    func setBusy(_ cameraBusy: Bool) {
        let value = cameraBusy || updateBusy
        updateButton.isEnabled = !value
        settingsButton.isEnabled = !value
        downloadUpdateButton.isEnabled = !value && !updateVersion.isEmpty
        prankCheckbox.isEnabled = !value && connectionVerified && detectedModel == "907X & CFV 100C"
        for choice in featureChoices.values { choice.isEnabled = !value }
        let labels = language == "en" ? ["afc": "AF-C", "speed-buff": "Focus speed", "auto-rear-brightness": "Auto brightness"] : ["afc": "AF-C", "speed-buff": "对焦加速", "auto-rear-brightness": "后屏自动亮度"]
        featureCount.stringValue = translated("已选择 ") + String(selectedFeatures.count) + translated(" 项")
        logState.stringValue = translated(value ? "操作进行中" : connectionVerified ? "检查通过" : "等待连接")
        prankCheckbox.isHidden = detectedModel != "907X & CFV 100C"
        desktopFields["dependency"]?.isHidden = !prankCheckbox.isHidden
        if let canvas = window.contentView as? ToolkitCanvas { canvas.language = language; canvas.busy = value; canvas.verified = connectionVerified; canvas.needsDisplay = true }
        selectionSummary.stringValue = selectedFeatures.isEmpty ? translated("尚未选择功能") : selectedFeatures.map { translated(labels[$0]!) }.joined(separator: language == "en" ? ", " : "、")
        install.isEnabled = !value && connectionVerified && !selectedFeatures.isEmpty
        restore.isEnabled = !value && connectionVerified; refresh.isEnabled = !value
    }
    func appendLog(_ line: String) {
        // Camera identities never appear in the main UI; private logs stay local.
        logBuffer += line + "\n"
        renderLog()
    }
    func consume(_ line: String) {
        if line.hasPrefix("X2D_EVENT "),
           let data = String(line.dropFirst(10)).data(using: .utf8),
           let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] {
            let kind = object["type"] as? String ?? ""
            let message = object["message"] as? String ?? ""
            if kind == "confirmation" {
                guard currentAction == "install", task?.isRunning == true,
                      object["language"] as? String == installLanguage,
                      let input = confirmationInput,
                      let title = object["title"] as? String, let body = object["body"] as? String,
                      let cancel = object["cancel"] as? String, let proceed = object["proceed"] as? String else {
                    try? confirmationInput?.write(contentsOf: Data("CANCEL_REINSTALL\n".utf8))
                    return
                }
                let alert = NSAlert()
                alert.alertStyle = .warning
                alert.messageText = title; alert.informativeText = body
                alert.addButton(withTitle: cancel).keyEquivalent = "\r"
                alert.addButton(withTitle: proceed).keyEquivalent = ""
                alert.beginSheetModal(for: window) { response in
                    let reply = response == .alertSecondButtonReturn ? "CONFIRM_REINSTALL\n" : "CANCEL_REINSTALL\n"
                    try? input.write(contentsOf: Data(reply.utf8))
                }
                return
            } else if kind == "cancelled" {
                receivedResult = true; pendingUserHint = nil
                setLocalized(status, message); setLocalized(detail, message)
                progress.doubleValue = 0
            } else if kind == "progress" {
                setLocalized(status, currentAction == "install" ? "正在安装…" : currentAction == "restore" ? "正在恢复…" : "正在检查相机…")
                setLocalized(detail, message)
                progress.doubleValue = (object["percent"] as? Double) ?? 0
            } else if kind == "status" {
                detectedModel = object["model"] as? String ?? ""
                if detectedModel != "907X & CFV 100C" { prankCheckbox.state = .off }
                connectionVerified = object["connected"] as? Bool == true && object["firmware"] as? String == "4.2.0"
                setLocalized(status, message)
                setLocalized(detail, object["menuPending"] as? Bool == true ? (object["hint"] as? String ?? "") : (object["installed"] as? Bool == true)
                    ? "主菜单末尾进入耍起功能。总开关控制已安装的功能。"
                    : "相机处于原厂状态，可以安装耍起功能。")
                progress.doubleValue = 0
                receivedResult = true
                if connectionVerified {
                    pendingUserHint = object["menuPending"] as? Bool == true ? (object["hint"] as? String ?? "") : object["recovery"] as? Bool == true
                        ? "相机检查完成。请点击“一键恢复原状”，完成上次操作的恢复。"
                        : object["installed"] as? Bool == true
                            ? "相机检查完成，耍起功能已安装。可在相机主菜单末尾使用功能；如需撤回，请点击“一键恢复原状”。"
                            : "相机检查完成。请选择要安装的功能，再点击“安装所选功能”。"
                }
            } else if kind == "result" {
                setLocalized(status, message); progress.doubleValue = 100; receivedResult = true
                setLocalized(detail, (object["installed"] as? Bool == true)
                    ? "安装已校验。请在相机菜单中开启已安装的功能。"
                    : "原厂界面与启动配置已恢复。")
                if object["success"] as? Bool == true {
                    pendingUserHint = object["installed"] as? Bool == true
                        ? "操作已完成，可以拔掉相机的 USB 数据线。请在相机主菜单末尾进入“耍起功能”，先开启总开关，再开启已安装的功能。"
                        : "恢复已完成，可以拔掉相机的 USB 数据线，继续使用原厂功能。"
                }
            } else if kind == "error" {
                connectionVerified = false; detectedModel = ""; prankCheckbox.state = .off
                setLocalized(status, currentAction == "status" ? "未能读取相机状态" : "操作未完成")
                setLocalized(detail, message)
                receivedResult = true
            }
            appendLog(message)
            if kind == "progress", !showedRestartHint,
               (object["percent"] as? Double) == 85 {
                showedRestartHint = true
                appendLog("请保持数据线连接，等待相机重启及校验完成。如相机屏幕出现“跳过”按钮，请点击“跳过”。")
            }
            if kind == "error" {
                pendingUserHint = nil
                appendLog(currentAction == "status"
                    ? "请确认相机已开机并插好数据线；如屏幕出现“跳过”请点击，再点击 App 中的“已连接”重新检查。"
                    : "请保持相机连接，点击“已连接”重新检查状态；如提示上次操作未完成，请按提示使用“一键恢复原状”。")
            }
        } // Only structured Chinese messages enter the visible log.
    }
    func run(_ action: String) {
        guard task == nil, !updateBusy, let resources = Bundle.main.resourceURL else { return }
        if action == "install" && selectedFeatures.isEmpty { return }
        if action != "status" && !connectionVerified {
            setLocalized(detail, "请先点击“已连接”，检查相机连接与状态。")
            appendLog("请先点击“已连接”，检查相机连接与状态。")
            return
        }
        if action == "status" { connectionVerified = false; detectedModel = ""; prankCheckbox.state = .off }
        setBusy(true); currentAction = action; receivedResult = false; outputBuffer = ""
        pendingUserHint = nil; showedRestartHint = false
        appendLog(action == "status"
            ? "正在检查相机连接与状态，请保持数据线连接；如相机屏幕出现“跳过”请点击。"
            : "已开始" + (action == "install" ? "安装" : "恢复") + "。请保持相机供电和数据线连接，等待 App 提示完成后再拔线。")
        setLocalized(status, action == "install" ? "准备安装…" : action == "restore" ? "准备恢复…" : "正在检查相机…")
        progress.doubleValue = 0
        let worker = Process()
        worker.executableURL = resources.appendingPathComponent("runtime/bin/python3.13")
        worker.arguments = ["-B", "-u", resources.appendingPathComponent("x2d_play_software.py").path, action]
        installLanguage = language
        if action == "install" {
            worker.arguments! += ["--language", installLanguage, "--interactive-confirmation"]
            worker.arguments! += ["--features"] + selectedFeatures
            let input = Pipe()
            worker.standardInput = input
            confirmationInput = input.fileHandleForWriting
        }
        if action == "install" && detectedModel == "907X & CFV 100C" && prankCheckbox.state == .on {
            worker.arguments!.append("--prank-ibis")
            appendLog("已选择 907 防抖彩蛋：第 11 格为彩蛋，第 12 格为耍起功能。")
        }
        var environment = ProcessInfo.processInfo.environment
        environment.removeValue(forKey: "X2D_PAYLOAD_DIR")
        environment["PYTHONHOME"] = resources.appendingPathComponent("runtime").path
        environment["PYTHONPATH"] = resources.path
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PATH"] = resources.appendingPathComponent("bin").path + ":/usr/bin:/bin:/usr/sbin:/sbin"
        worker.environment = environment
        let pipe = Pipe(); worker.standardOutput = pipe; worker.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { handle.readabilityHandler = nil; return }
            let text = String(decoding: data, as: UTF8.self)
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.outputBuffer += text
                while let range = self.outputBuffer.range(of: "\n") {
                    self.consume(String(self.outputBuffer[..<range.lowerBound]))
                    self.outputBuffer.removeSubrange(self.outputBuffer.startIndex..<range.upperBound)
                }
            }
        }
        worker.terminationHandler = { [weak self] process in
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                guard let self = self else { return }
                if !self.outputBuffer.isEmpty { self.consume(self.outputBuffer); self.outputBuffer = "" }
                if process.terminationStatus != 0 && !self.receivedResult {
                    self.connectionVerified = false
                    self.setLocalized(self.status, "操作未完成")
                    self.setLocalized(self.detail, "请检查 USB 连接后重新点击“已连接”。")
                    self.appendLog("操作未完成，请检查 USB 连接后重试。")
                }
                try? self.confirmationInput?.close(); self.confirmationInput = nil
                self.task = nil; self.setBusy(false)
                if process.terminationStatus == 0, self.receivedResult, let hint = self.pendingUserHint {
                    self.appendLog(hint)
                }
                self.pendingUserHint = nil
            }
        }
        task = worker
        do { try worker.run() }
        catch { try? confirmationInput?.close(); confirmationInput = nil; task = nil; connectionVerified = false; setBusy(false); setLocalized(status, "无法启动应用运行时"); setLocalized(detail, "应用运行环境无法启动，请重新解压完整安装包。"); appendLog("应用运行环境无法启动，请重新解压完整安装包。") }
    }
    func appendUpdateNotice() {
        let fm = FileManager.default
        let target = Bundle.main.bundleURL.resolvingSymlinksInPath()
        guard let folders = try? fm.contentsOfDirectory(at: target.deletingLastPathComponent(), includingPropertiesForKeys: [.contentModificationDateKey]) else { return }
        let sorted = folders.filter { $0.lastPathComponent.hasPrefix(".toolkit-update-") }.sorted {
            let a = (try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let b = (try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return a > b
        }
        for folder in sorted {
            if fm.fileExists(atPath: folder.appendingPathComponent("notified").path) { continue }
            guard let planData = try? Data(contentsOf: folder.appendingPathComponent("plan.json")),
                  let plan = (try? JSONSerialization.jsonObject(with: planData)) as? [String: Any],
                  plan["target"] as? String == target.path,
                  let resultData = try? Data(contentsOf: folder.appendingPathComponent("result.json")),
                  let result = (try? JSONSerialization.jsonObject(with: resultData)) as? [String: Any],
                  let success = result["success"] as? Bool else { continue }
            if !fm.createFile(atPath: folder.appendingPathComponent("notified").path, contents: Data()) { continue }
            appendLog(success ? "软件更新安装完成，上一版已保留在应用旁的更新备份目录"
                              : "软件更新未能安装，已保留或恢复上一版；请关闭占用软件的程序后重试")
            break
        }
    }
    @objc func updateClicked() {
        runUpdate(install: false)
    }
    @objc func downloadUpdateClicked() {
        guard !updateVersion.isEmpty else { return }
        runUpdate(install: true)
    }
    func runUpdate(install: Bool) {
        guard task == nil, !updateBusy, let resources = Bundle.main.resourceURL else { return }
        updateBusy = true; setBusy(false)
        let worker = Process()
        worker.executableURL = resources.appendingPathComponent("runtime/bin/python3.13")
        worker.arguments = ["-B", "-u", resources.appendingPathComponent("app_updates.py").path,
                            install ? "install" : "check", "--current", appVersion,
                            "--platform", "mac", "--target", Bundle.main.bundleURL.path,
                            "--parent", String(ProcessInfo.processInfo.processIdentifier)]
        if install { worker.arguments! += ["--wanted", updateVersion] }
        var env = ProcessInfo.processInfo.environment
        env.removeValue(forKey: "X2D_PAYLOAD_DIR")
        env["PYTHONHOME"] = resources.appendingPathComponent("runtime").path
        env["PYTHONPATH"] = resources.path; env["PYTHONNOUSERSITE"] = "1"
        worker.environment = env
        let pipe = Pipe(); worker.standardOutput = pipe; worker.standardError = FileHandle.nullDevice
        var buffer = ""
        var gotResult = false
        func consumeUpdate(_ line: String) {
            guard line.hasPrefix("TOOLKIT_UPDATE "),
                  let data = String(line.dropFirst(15)).data(using: .utf8),
                  let event = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return }
            let kind = event["type"] as? String ?? ""
            let message = event["message"] as? String ?? ""
            self.appendLog(message); self.setLocalized(self.detail, message)
            self.setLocalized(self.settingsUpdateStatus, message)
            self.progress.doubleValue = event["percent"] as? Double ?? 0
            if kind == "available" {
                self.updateVersion = event["version"] as? String ?? ""
                self.setLocalized(self.status, "发现软件新版本：" + self.updateVersion)
                gotResult = true
            } else if kind == "current" {
                self.updateVersion = ""; self.setLocalized(self.status, message); gotResult = true
            } else if kind == "error" {
                self.updateVersion = ""; self.setLocalized(self.status, "软件更新未完成"); gotResult = true
            } else if kind == "restart" {
                gotResult = true; self.updateRestarting = true; NSApp.terminate(nil)
            }
            self.renderLanguage()
        }
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            DispatchQueue.main.async {
                buffer += String(decoding: data, as: UTF8.self)
                while let range = buffer.range(of: "\n") {
                    consumeUpdate(String(buffer[..<range.lowerBound]))
                    buffer.removeSubrange(buffer.startIndex..<range.upperBound)
                }
            }
        }
        worker.terminationHandler = { _ in
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                if !buffer.isEmpty { consumeUpdate(buffer); buffer = "" }
                if !gotResult {
                    let message = "软件更新未完成，请检查网络连接或重新下载完整安装包；当前应用仍保留"
                    self.appendLog(message); self.setLocalized(self.detail, message)
                }
                self.updateTask = nil; self.updateBusy = false; self.setBusy(false)
            }
        }
        updateTask = worker
        do { try worker.run() }
        catch {
            updateTask = nil; updateBusy = false; setBusy(false)
            appendLog("应用运行环境无法启动，请重新解压完整安装包。")
        }
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if task != nil || updateBusy { setLocalized(detail, "操作尚未结束，请等待完成后关闭应用。"); return false }
        return true
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if updateRestarting { return .terminateNow }
        if task != nil || updateBusy { setLocalized(detail, "操作尚未结束，请等待完成后退出应用。"); return .terminateCancel }
        return .terminateNow
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
