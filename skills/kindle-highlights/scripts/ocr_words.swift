import Foundation
import Vision
import AppKit

// Usage: ocr_words <image.png>  — JSON lines: one object per text line with normalized (top-left origin) box + per-word boxes.
guard CommandLine.arguments.count >= 2 else { FileHandle.standardError.write("usage: ocr_words <image.png>\n".data(using: .utf8)!); exit(1) }
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path), let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff), let cg = rep.cgImage else { FileHandle.standardError.write("cannot load image\n".data(using: .utf8)!); exit(1) }
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([request])

struct W: Codable { let t: String; let x0: Double; let x1: Double; let y0: Double; let y1: Double }
struct L: Codable { let text: String; let x0: Double; let x1: Double; let y0: Double; let y1: Double; let conf: Double; let words: [W] }
var lines: [L] = []
for obs in request.results ?? [] {
    guard let cand = obs.topCandidates(1).first else { continue }
    let s = cand.string
    let b = obs.boundingBox
    var words: [W] = []
    // split on spaces, keeping ranges
    var idx = s.startIndex
    while idx < s.endIndex {
        while idx < s.endIndex && s[idx] == " " { idx = s.index(after: idx) }
        if idx >= s.endIndex { break }
        var j = idx
        while j < s.endIndex && s[j] != " " { j = s.index(after: j) }
        let r = idx..<j
        if let wb = try? cand.boundingBox(for: r) {
            let bb = wb.boundingBox
            words.append(W(t: String(s[r]), x0: bb.minX, x1: bb.maxX, y0: 1.0 - bb.maxY, y1: 1.0 - bb.minY))
        } else {
            words.append(W(t: String(s[r]), x0: -1, x1: -1, y0: -1, y1: -1))
        }
        idx = j
    }
    lines.append(L(text: s, x0: b.minX, x1: b.maxX, y0: 1.0 - b.maxY, y1: 1.0 - b.minY, conf: Double(cand.confidence), words: words))
}
lines.sort { a, b in if abs(a.y0 - b.y0) > 0.006 { return a.y0 < b.y0 }; return a.x0 < b.x0 }
let enc = JSONEncoder()
for l in lines { if let d = try? enc.encode(l), let s = String(data: d, encoding: .utf8) { print(s) } }
