// Fast OCR using Apple's Vision framework.
// Usage: ocr [--fast] [--lang fr-FR,en-US] < paths.txt
// Prints one JSON object per image (JSON Lines), in completion order.
// Boxes are normalized (0-1) with origin at top-left.
// Vision serializes work inside one process, so callers should run several
// processes in parallel for throughput.

import Foundation
import ImageIO
import Vision

var fastMode = false
var languages = ["fr-FR", "en-US"]
var paths: [String] = []

var it = CommandLine.arguments.dropFirst().makeIterator()
while let arg = it.next() {
    switch arg {
    case "--fast": fastMode = true
    case "--lang": if let v = it.next() { languages = v.split(separator: ",").map(String.init) }
    default: paths.append(arg)
    }
}
if paths.isEmpty {
    while let line = readLine() {
        if !line.isEmpty { paths.append(line) }
    }
}

func emit(_ obj: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: obj),
          let s = String(data: data, encoding: .utf8) else { return }
    print(s)
    fflush(stdout)
}

for path in paths {
    autoreleasepool {
        guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
            emit(["file": path, "error": "cannot decode image"])
            return
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = fastMode ? .fast : .accurate
        request.recognitionLanguages = languages
        request.usesLanguageCorrection = false
        request.minimumTextHeight = 0.012
        do {
            try VNImageRequestHandler(cgImage: image).perform([request])
        } catch {
            emit(["file": path, "error": "\(error)"])
            return
        }
        let lines: [[String: Any]] = (request.results ?? []).compactMap { obs in
            guard let cand = obs.topCandidates(1).first else { return nil }
            let b = obs.boundingBox
            return [
                "t": cand.string,
                "c": Double(cand.confidence),
                "x": Double(b.minX), "y": Double(1 - b.maxY),
                "w": Double(b.width), "h": Double(b.height),
            ]
        }
        emit(["file": path, "w": image.width, "h": image.height, "lines": lines])
    }
}
