// Native fixture window discovery, restricted mouse input, and sRGB inspection.
import AppKit
import CoreGraphics
import Foundation
import Vision

func emit(_ value: Any) throws {
    let bytes = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    print(String(data: bytes, encoding: .utf8)!)
}
// Input is restricted to a freshly created, uniquely titled fixture window.
func fixture(_ title: String, _ id: Int) throws -> [String: Any] {
    guard title.hasPrefix("Ithilien evaluation "),
          let list = CGWindowListCopyWindowInfo([.optionAll, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        throw NSError(domain: "GhosttyInput", code: 1)
    }
    let matches = list.filter {
        ($0[kCGWindowOwnerName as String] as? String) == "Ghostty" &&
        ($0[kCGWindowName as String] as? String) == title &&
        ($0[kCGWindowLayer as String] as? Int) == 0
    }
    guard matches.count == 1, (matches[0][kCGWindowNumber as String] as? Int) == id else {
        throw NSError(domain: "GhosttyInput", code: 2, userInfo: [NSLocalizedDescriptionKey: "Fixture identity changed; refusing input"])
    }
    return matches[0]
}
func focusFixture(_ title: String, _ id: Int) throws -> [String: Any] {
    guard AXIsProcessTrusted() else {
        throw NSError(domain: "GhosttyInput", code: 3, userInfo: [NSLocalizedDescriptionKey: "Accessibility permission is unavailable; grant it to the capture helper in System Settings"])
    }
    let info = try fixture(title, id)
    let pid = info[kCGWindowOwnerPID as String] as! Int32
    guard let app = NSRunningApplication(processIdentifier: pid) else { throw NSError(domain: "GhosttyInput", code: 4) }
    if NSWorkspace.shared.frontmostApplication?.processIdentifier != pid {
        app.activate(options: [])
        Thread.sleep(forTimeInterval: 0.2)
    }
    let ax = AXUIElementCreateApplication(pid)
    // The CG window may be published before its Accessibility counterpart.
    // Retry identity lookup, never fall back to another window or global keys.
    let deadline = Date().addingTimeInterval(3)
    var raised = false
    repeat {
        _ = try fixture(title, id)
        var value: CFTypeRef?
        if AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute as CFString, &value) == .success,
           let windows = value as? [AXUIElement] {
            let matches = windows.filter { window in
                var name: CFTypeRef?
                return AXUIElementCopyAttributeValue(window, kAXTitleAttribute as CFString, &name) == .success && (name as? String) == title
            }
            if matches.count == 1 && AXUIElementPerformAction(matches[0], kAXRaiseAction as CFString) == .success {
                raised = true
                break
            }
        }
        Thread.sleep(forTimeInterval: 0.1)
    } while Date() < deadline
    guard raised else {
        throw NSError(domain: "GhosttyInput", code: 6, userInfo: [NSLocalizedDescriptionKey: "Cannot raise exact fixture window"])
    }
    let focusDeadline = Date().addingTimeInterval(3)
    while NSWorkspace.shared.frontmostApplication?.processIdentifier != pid && Date() < focusDeadline {
        Thread.sleep(forTimeInterval: 0.1)
    }
    guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else {
        throw NSError(domain: "GhosttyInput", code: 7, userInfo: [NSLocalizedDescriptionKey: "Fixture did not receive focus"])
    }
    return try fixture(title, id)
}
func dragFixture(_ title: String, _ id: Int, _ fractions: [Double]) throws {
    let info = try focusFixture(title, id)
    guard fractions.count == 4, fractions.allSatisfy({ $0.isFinite && $0 > 0 && $0 < 1 }),
          let dictionary = info[kCGWindowBounds as String] as? NSDictionary,
          let bounds = CGRect(dictionaryRepresentation: dictionary) else { throw NSError(domain: "GhosttyInput", code: 8) }
    let pid = info[kCGWindowOwnerPID as String] as! Int32
    let start = CGPoint(x: bounds.minX + fractions[0]*bounds.width, y: bounds.minY + fractions[1]*bounds.height)
    let end = CGPoint(x: bounds.minX + fractions[2]*bounds.width, y: bounds.minY + fractions[3]*bounds.height)
    // Recheck ownership before each event; always release the mouse on error.
    var last = start
    func post(_ type: CGEventType, _ point: CGPoint) throws {
        _ = try fixture(title, id)
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid,
              let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]],
              let hit = list.first(where: { item in
                  guard (item[kCGWindowLayer as String] as? Int) == 0,
                        let d = item[kCGWindowBounds as String] as? NSDictionary,
                        let r = CGRect(dictionaryRepresentation: d) else { return false }
                  return r.contains(point)
              }), (hit[kCGWindowNumber as String] as? Int) == id,
              let event = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: point, mouseButton: .left) else {
            throw NSError(domain: "GhosttyInput", code: 9, userInfo: [NSLocalizedDescriptionKey: "Fixture lost focus or is occluded; refusing mouse input"])
        }
        event.flags = []
        event.setIntegerValueField(.mouseEventClickState, value: 1)
        event.post(tap: .cghidEventTap)
        last = point
    }
    try post(.mouseMoved, start)
    try post(.leftMouseDown, start)
    defer {
        CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: last, mouseButton: .left)?.post(tap: .cghidEventTap)
    }
    for step in 1...12 {
        let t = Double(step)/12
        try post(.leftMouseDragged, CGPoint(x: start.x+(end.x-start.x)*t, y: start.y+(end.y-start.y)*t))
        Thread.sleep(forTimeInterval: 0.02)
    }
}

let args = Array(CommandLine.arguments.dropFirst())
do {
    if args.first == "frontmost" {
        try emit(["pid": NSWorkspace.shared.frontmostApplication?.processIdentifier ?? -1])
    } else if args.first == "deactivate", args.count == 4, let id = Int(args[2]), let previous = Int32(args[3]) {
        let owned = try fixture(args[1], id)
        let pid = owned[kCGWindowOwnerPID as String] as! Int32
        guard previous != pid, let app = NSRunningApplication(processIdentifier: previous) else {
            throw NSError(domain: "GhosttyInput", code: 11, userInfo: [NSLocalizedDescriptionKey: "Original foreground application is unavailable"])
        }
        app.activate(options: [])
        Thread.sleep(forTimeInterval: 0.3)
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == previous else {
            throw NSError(domain: "GhosttyInput", code: 12, userInfo: [NSLocalizedDescriptionKey: "Fixture did not become inactive"])
        }
        try emit(["inactive": true, "restored_pid": previous])
    } else if args.first == "close", args.count == 3, let id = Int(args[2]) {
        // Close only the exact, uniquely titled evaluation window. Never quit
        // Ghostty or send a shortcut to whichever window happens to be active.
        guard AXIsProcessTrusted() else {
            throw NSError(domain: "GhosttyInput", code: 3, userInfo: [NSLocalizedDescriptionKey: "Accessibility permission is unavailable for fixture cleanup"])
        }
        let info = try fixture(args[1], id)
        let pid = info[kCGWindowOwnerPID as String] as! Int32
        var value: CFTypeRef?
        let ax = AXUIElementCreateApplication(pid)
        guard AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute as CFString, &value) == .success,
              let windows = value as? [AXUIElement] else { throw NSError(domain: "GhosttyInput", code: 5) }
        let matches = windows.filter { window in
            var name: CFTypeRef?
            return AXUIElementCopyAttributeValue(window, kAXTitleAttribute as CFString, &name) == .success && (name as? String) == args[1]
        }
        guard matches.count == 1 else { throw NSError(domain: "GhosttyInput", code: 2) }
        var button: CFTypeRef?
        guard AXUIElementCopyAttributeValue(matches[0], kAXCloseButtonAttribute as CFString, &button) == .success,
              let button = button,
              AXUIElementPerformAction(button as! AXUIElement, kAXPressAction as CFString) == .success else {
            throw NSError(domain: "GhosttyInput", code: 10, userInfo: [NSLocalizedDescriptionKey: "Could not close exact fixture window"])
        }
        try emit(["closed": true])
    } else if args.first == "focus", args.count == 3, let id = Int(args[2]) {
        _ = try focusFixture(args[1], id)
        try emit(["focused": true])
    } else if args.first == "drag", args.count == 7, let id = Int(args[2]) {
        let fractions = args.dropFirst(3).compactMap(Double.init)
        try dragFixture(args[1], id, fractions)
        try emit(["dragged": true])
    } else if args.first == "windows", args.count == 2 {
        guard CGPreflightScreenCaptureAccess() else {
            throw NSError(domain: "GhosttyCapture", code: 1, userInfo: [NSLocalizedDescriptionKey: "Screen Recording permission is unavailable"])
        }
        let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
        let matches = windows.filter {
            ($0[kCGWindowOwnerName as String] as? String) == "Ghostty" &&
            ($0[kCGWindowName as String] as? String) == args[1] &&
            ($0[kCGWindowLayer as String] as? Int) == 0
        }.compactMap { $0[kCGWindowNumber as String] as? Int }
        try emit(["windows": matches])
    } else if args.first == "ocr-rows", args.count == 2 {
        let data = try Data(contentsOf: URL(fileURLWithPath: args[1]))
        let inputs = try JSONSerialization.jsonObject(with: data) as! [[String: Any]]
        var output: [[String: Any]] = []
        for input in inputs {
            let path = input["path"] as! String
            guard let image = NSImage(contentsOfFile: path),
                  let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
                throw NSError(domain: "GhosttyCapture", code: 2)
            }
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = false
            request.recognitionLanguages = ["en-US"]
            try VNImageRequestHandler(cgImage: cg).perform([request])
            let fragments = (request.results ?? []).sorted { $0.boundingBox.minX < $1.boundingBox.minX }.compactMap { item -> [String: Any]? in
                guard let text = item.topCandidates(1).first else { return nil }
                return ["text": text.string, "confidence": text.confidence]
            }
            output.append(["row": input["row"]!, "fragments": fragments])
        }
        try emit(["rows": output])
    } else if args.first == "ocr", args.count == 2 {
        guard let image = NSImage(contentsOfFile: args[1]),
              let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            throw NSError(domain: "GhosttyCapture", code: 2)
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["en-US"]
        try VNImageRequestHandler(cgImage: cg).perform([request])
        let lines = (request.results ?? []).compactMap { item -> [String: Any]? in
            guard let text = item.topCandidates(1).first else { return nil }
            let b = item.boundingBox
            return ["text": text.string, "confidence": text.confidence,
                    "box": [b.minX, b.minY, b.width, b.height]]
        }
        try emit(["lines": lines])
    } else if args.first == "pixels", args.count >= 3 {
        guard let image = NSImage(contentsOfFile: args[1]),
              let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil),
              let space = CGColorSpace(name: CGColorSpace.sRGB) else {
            throw NSError(domain: "GhosttyCapture", code: 2, userInfo: [NSLocalizedDescriptionKey: "Cannot decode screenshot"])
        }
        let width = cg.width, height = cg.height
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        let targets = args.dropFirst(2).map { value -> (String, Int, Int, Int) in
            let n = UInt32(value.dropFirst(), radix: 16)!
            return (value, Int((n >> 16) & 255), Int((n >> 8) & 255), Int(n & 255))
        }
        var counts = Dictionary(uniqueKeysWithValues: targets.map { ($0.0, 0) })
        try pixels.withUnsafeMutableBytes { data in
            guard let ctx = CGContext(data: data.baseAddress, width: width, height: height,
                                      bitsPerComponent: 8, bytesPerRow: width * 4, space: space,
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue | CGBitmapInfo.byteOrder32Big.rawValue) else {
                throw NSError(domain: "GhosttyCapture", code: 3)
            }
            ctx.draw(cg, in: CGRect(x: 0, y: 0, width: width, height: height))
            let buffer = data.bindMemory(to: UInt8.self)
            for i in stride(from: 0, to: buffer.count, by: 4) where buffer[i+3] == 255 {
                for (key, r, g, b) in targets where abs(Int(buffer[i])-r) <= 2 && abs(Int(buffer[i+1])-g) <= 2 && abs(Int(buffer[i+2])-b) <= 2 {
                    counts[key, default: 0] += 1
                }
            }
        }
        try emit(["width": width, "height": height, "color_space": "sRGB", "counts": counts])
    } else {
        throw NSError(domain: "GhosttyCapture", code: 4, userInfo: [NSLocalizedDescriptionKey: "Expected windows TITLE or pixels PNG HEX..."])
    }
} catch {
    fputs("\(error.localizedDescription)\n", stderr)
    exit(1)
}
