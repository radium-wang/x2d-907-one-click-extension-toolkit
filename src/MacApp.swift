import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    let status = NSTextField(labelWithString: "等待连接相机")
    let detail = NSTextField(wrappingLabelWithString: "连接相机并开机，点击“已连接”检查状态。907X 100C 适配版待实机验证。")
    let progress = NSProgressIndicator()
    let install = NSButton(title: "一键安装", target: nil, action: nil)
    let restore = NSButton(title: "一键恢复原状", target: nil, action: nil)
    let refresh = NSButton(title: "已连接", target: nil, action: nil)
    let logs = NSTextView()
    let prankCheckbox = NSButton(checkboxWithTitle: "添加防抖功能（907 彩蛋）", target: nil, action: nil)
    var detectedModel = ""
    var task: Process?
    var logBuffer = ""
    var language = UserDefaults.standard.string(forKey: "AppLanguage") == "en" ? "en" : "zh"
    var translations: [String: String] = [:]
    var fragments: [String] = []
    var localizedImages: [(NSImageView, String)] = []
    var localizedFields: [ObjectIdentifier: (NSTextField, String)] = [:]
    let languageChoice = NSPopUpButton(frame: .zero, pullsDown: false)
    var quitItem: NSMenuItem!
    var appVersion = ""
    let updateButton = NSButton(title: "检查更新", target: nil, action: nil)
    var updateVersion = ""
    var updateBusy = false
    var updateRestarting = false
    var updateTask: Process?

    func translated(_ text: String) -> String {
        if language != "en" { return text.replacingOccurrences(of: "Windows", with: "系统") }
        var value = translations[text] ?? text
        if translations[text] == nil {
            for key in fragments where value.contains(key) {
                value = value.replacingOccurrences(of: key, with: translations[key]!)
            }
        }
        return value.replacingOccurrences(of: "Windows", with: "the system")
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
        for (field, source) in localizedFields.values { field.stringValue = translated(source) }
        for (image, source) in localizedImages { image.setAccessibilityLabel(translated(source)) }
        prankCheckbox.title = translated("添加防抖功能（907 彩蛋）")
        updateButton.title = translated(updateVersion.isEmpty ? "检查更新" : "下载并安装更新")
        refresh.title = translated("已连接")
        install.title = translated("一键安装")
        restore.title = translated("一键恢复原状")
        quitItem.title = translated("退出 x2d/907一键扩展功能-工具包")
        window.title = translated("x2d/907一键扩展功能-工具包 · ") + appVersion
        languageChoice.selectItem(at: language == "en" ? 1 : 0)
        renderLog()
    }
    @objc func languageChanged() {
        language = languageChoice.indexOfSelectedItem == 1 ? "en" : "zh"
        UserDefaults.standard.set(language, forKey: "AppLanguage")
        renderLanguage()
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
        NSApp.setActivationPolicy(.regular)
        let mainMenu = NSMenu()
        let applicationItem = NSMenuItem()
        let applicationMenu = NSMenu()
        quitItem = NSMenuItem(title: "退出 x2d/907一键扩展功能-工具包", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        applicationMenu.addItem(quitItem)
        applicationItem.submenu = applicationMenu
        mainMenu.addItem(applicationItem)
        NSApp.mainMenu = mainMenu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 580, height: 754),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "未知"
        appVersion = version
        window.title = "x2d/907一键扩展功能-工具包 · " + version
        window.delegate = self
        window.center()
        let root = NSStackView()
        root.orientation = .vertical; root.spacing = 12; root.alignment = .leading
        root.edgeInsets = NSEdgeInsets(top: 28, left: 28, bottom: 24, right: 28)
        root.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(root)
        NSLayoutConstraint.activate([
            root.topAnchor.constraint(equalTo: window.contentView!.topAnchor),
            root.bottomAnchor.constraint(equalTo: window.contentView!.bottomAnchor),
            root.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor)
        ])
        let heading = NSTextField(labelWithString: "x2d/907一键扩展功能-工具包")
        heading.font = .systemFont(ofSize: 22, weight: .semibold)
        localize(heading)
        languageChoice.addItems(withTitles: ["中文", "English"])
        languageChoice.target = self
        languageChoice.action = #selector(languageChanged)
        languageChoice.setAccessibilityLabel("语言 / Language")
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let header = NSStackView(views: [heading, spacer, languageChoice])
        header.orientation = .horizontal; header.alignment = .centerY
        root.addArrangedSubview(header)
        header.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -56).isActive = true
        let subtitle = NSTextField(labelWithString: "X2D 100C / 907X 100C · 固件 4.2.0")
        subtitle.font = .systemFont(ofSize: 14); subtitle.textColor = .secondaryLabelColor
        localize(subtitle)
        root.addArrangedSubview(subtitle)
        let featureBox = NSBox()
        featureBox.boxType = .custom; featureBox.titlePosition = .noTitle
        featureBox.borderType = .lineBorder; featureBox.borderColor = .separatorColor
        featureBox.fillColor = .controlBackgroundColor; featureBox.cornerRadius = 10
        featureBox.contentViewMargins = .zero
        let featureList = NSStackView(views: [
            featureRow("viewfinder", "AF-C 连续自动对焦", "在相机上开启连续自动对焦"),
            featureRow("bolt", "对焦加速 buff", "加快对焦扫描，关闭后恢复原厂速度")
        ])
        featureList.orientation = .vertical; featureList.spacing = 12; featureList.alignment = .leading
        featureList.translatesAutoresizingMaskIntoConstraints = false
        featureBox.contentView!.addSubview(featureList)
        NSLayoutConstraint.activate([
            featureList.topAnchor.constraint(equalTo: featureBox.contentView!.topAnchor, constant: 14),
            featureList.bottomAnchor.constraint(equalTo: featureBox.contentView!.bottomAnchor, constant: -14),
            featureList.leadingAnchor.constraint(equalTo: featureBox.contentView!.leadingAnchor, constant: 14),
            featureList.trailingAnchor.constraint(equalTo: featureBox.contentView!.trailingAnchor, constant: -14)
        ])
        root.addArrangedSubview(featureBox)
        featureBox.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -56).isActive = true
        featureBox.heightAnchor.constraint(equalToConstant: 116).isActive = true
        prankCheckbox.isEnabled = false
        prankCheckbox.state = .off
        root.addArrangedSubview(prankCheckbox)
        localize(status); localize(detail)
        status.font = .systemFont(ofSize: 16, weight: .medium)
        root.addArrangedSubview(status)
        detail.font = .systemFont(ofSize: 13); detail.textColor = .secondaryLabelColor
        root.addArrangedSubview(detail)
        detail.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -56).isActive = true
        progress.minValue = 0; progress.maxValue = 100; progress.isIndeterminate = false
        progress.style = .bar; progress.controlSize = .small
        root.addArrangedSubview(progress)
        progress.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -56).isActive = true
        let buttons = NSStackView(views: [refresh, install, restore])
        buttons.orientation = .horizontal; buttons.spacing = 12
        for button in [install, restore, refresh] { button.bezelStyle = .rounded; button.controlSize = .large; button.target = self }
        install.action = #selector(installClicked); restore.action = #selector(restoreClicked); refresh.action = #selector(refreshClicked)
        refresh.keyEquivalent = "\r"
        root.addArrangedSubview(buttons)
        updateButton.bezelStyle = .rounded
        updateButton.target = self; updateButton.action = #selector(updateClicked)
        root.addArrangedSubview(updateButton)
        let warning = NSTextField(wrappingLabelWithString: "开启对焦 buff 后切勿取下镜头。\n更换镜头前，请先关闭对焦加速 buff。")
        localize(warning)
        warning.font = .systemFont(ofSize: 13, weight: .semibold)
        warning.textColor = .systemOrange
        root.addArrangedSubview(warning)
        warning.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -56).isActive = true
        let note = NSTextField(wrappingLabelWithString: "安装会自动保存原厂配置，并重启相机完成校验。恢复会撤回本应用的菜单与功能。请等待操作完成再拔线。")
        localize(note)
        note.font = .systemFont(ofSize: 12); note.textColor = .secondaryLabelColor
        root.addArrangedSubview(note)
        note.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -56).isActive = true
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true; scroll.borderType = .bezelBorder
        logs.isEditable = false; logs.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        logs.autoresizingMask = [.width]; logs.isHorizontallyResizable = false
        scroll.documentView = logs
        root.addArrangedSubview(scroll)
        scroll.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -56).isActive = true
        scroll.heightAnchor.constraint(greaterThanOrEqualToConstant: 90).isActive = true
        let directory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("X2DPlay")
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        logFile = directory.appendingPathComponent("latest.log")
        renderLanguage()
        window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        if CommandLine.arguments.contains("--ui-smoke-test") {
            setLocalized(status, "应用界面就绪")
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { NSApp.terminate(nil) }
        } else {
            setBusy(false)
            appendLog("应用版本：" + version)
            appendUpdateNotice()
            appendLog("请将相机开机，并通过 USB 数据线连接 Mac。")
            appendLog("如相机屏幕出现“跳过”按钮，请点击“跳过”，并保持数据线连接。")
            appendLog("连接好后，请点击 App 中的“已连接”；检查通过后即可操作。")
        }
    }

    func featureRow(_ symbol: String, _ title: String, _ description: String) -> NSView {
        let icon = NSImageView(image: NSImage(systemSymbolName: symbol, accessibilityDescription: title)!)
        localizedImages.append((icon, title))
        icon.contentTintColor = .secondaryLabelColor
        icon.widthAnchor.constraint(equalToConstant: 22).isActive = true
        icon.heightAnchor.constraint(equalToConstant: 22).isActive = true
        let name = NSTextField(labelWithString: title)
        localize(name)
        name.font = .systemFont(ofSize: 14, weight: .semibold)
        let caption = NSTextField(labelWithString: description)
        localize(caption)
        caption.font = .systemFont(ofSize: 12); caption.textColor = .secondaryLabelColor
        let text = NSStackView(views: [name, caption])
        text.orientation = .vertical; text.alignment = .leading; text.spacing = 3
        let row = NSStackView(views: [icon, text])
        row.orientation = .horizontal; row.alignment = .top; row.spacing = 12
        return row
    }

    @objc func installClicked() { run("install") }
    @objc func restoreClicked() { run("restore") }
    @objc func refreshClicked() { run("status") }

    func setBusy(_ cameraBusy: Bool) {
        let value = cameraBusy || updateBusy
        updateButton.isEnabled = !value
        prankCheckbox.isEnabled = !value && connectionVerified && detectedModel == "907X & CFV 100C"
        install.isEnabled = !value && connectionVerified; restore.isEnabled = !value && connectionVerified; refresh.isEnabled = !value
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
            if kind == "progress" {
                setLocalized(status, currentAction == "install" ? "正在安装…" : currentAction == "restore" ? "正在恢复…" : "正在检查相机…")
                setLocalized(detail, message)
                progress.doubleValue = (object["percent"] as? Double) ?? 0
            } else if kind == "status" {
                detectedModel = object["model"] as? String ?? ""
                if detectedModel != "907X & CFV 100C" { prankCheckbox.state = .off }
                connectionVerified = object["connected"] as? Bool == true && object["firmware"] as? String == "4.2.0"
                setLocalized(status, message)
                setLocalized(detail, object["menuPending"] as? Bool == true ? (object["hint"] as? String ?? "") : (object["installed"] as? Bool == true)
                    ? "主菜单末尾进入耍起功能。总开关控制 AF-C 与对焦加速 buff。"
                    : "相机处于原厂状态，可以安装耍起功能。")
                progress.doubleValue = 0
                receivedResult = true
                if connectionVerified {
                    pendingUserHint = object["menuPending"] as? Bool == true ? (object["hint"] as? String ?? "") : object["recovery"] as? Bool == true
                        ? "相机检查完成。请点击“一键恢复原状”，完成上次操作的恢复。"
                        : object["installed"] as? Bool == true
                            ? "相机检查完成，耍起功能已安装。可在相机主菜单末尾使用功能；如需撤回，请点击“一键恢复原状”。"
                            : "相机检查完成。现在可以点击“一键安装”安装耍起功能。"
                }
            } else if kind == "result" {
                setLocalized(status, message); progress.doubleValue = 100; receivedResult = true
                setLocalized(detail, (object["installed"] as? Bool == true)
                    ? "安装已校验。相机菜单中可分别开启 AF-C 与对焦加速 buff。"
                    : "原厂界面与启动配置已恢复。")
                if object["success"] as? Bool == true {
                    pendingUserHint = object["installed"] as? Bool == true
                        ? "操作已完成，可以拔掉相机的 USB 数据线。请在相机主菜单末尾进入“耍起功能”，先开启总开关，再选择 AF-C 或对焦加速 buff。"
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
                self.task = nil; self.setBusy(false)
                if process.terminationStatus == 0, self.receivedResult, let hint = self.pendingUserHint {
                    self.appendLog(hint)
                }
                self.pendingUserHint = nil
            }
        }
        task = worker
        do { try worker.run() }
        catch { task = nil; connectionVerified = false; setBusy(false); setLocalized(status, "无法启动应用运行时"); setLocalized(detail, "应用运行环境无法启动，请重新解压完整安装包。"); appendLog("应用运行环境无法启动，请重新解压完整安装包。") }
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
        guard task == nil, !updateBusy, let resources = Bundle.main.resourceURL else { return }
        updateBusy = true; setBusy(false)
        let worker = Process()
        worker.executableURL = resources.appendingPathComponent("runtime/bin/python3.13")
        worker.arguments = ["-B", "-u", resources.appendingPathComponent("app_updates.py").path,
                            updateVersion.isEmpty ? "check" : "install", "--current", appVersion,
                            "--platform", "mac", "--target", Bundle.main.bundleURL.path,
                            "--parent", String(ProcessInfo.processInfo.processIdentifier)]
        if !updateVersion.isEmpty { worker.arguments! += ["--wanted", updateVersion] }
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
