import Foundation
import Vision
import AppKit

// Usage: ocr <image.png> [minY maxY]  — prints recognized lines top-to-bottom with normalized bounding boxes.
guard CommandLine.arguments.count >= 2 else {
    FileHandle.standardError.write("usage: ocr <image.png>\n".data(using: .utf8)!)
    exit(1)
}
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let tiff = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: tiff),
      let cg = rep.cgImage else {
    FileHandle.standardError.write("cannot load image\n".data(using: .utf8)!)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([request])

struct Line { let y: CGFloat; let x: CGFloat; let text: String }
var lines: [Line] = []
for obs in request.results ?? [] {
    guard let cand = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox
    lines.append(Line(y: b.origin.y, x: b.origin.x, text: cand.string))
}
// sort top-to-bottom (Vision y is bottom-up), then left-to-right
lines.sort { a, b in
    if abs(a.y - b.y) > 0.008 { return a.y > b.y }
    return a.x < b.x
}
for l in lines {
    print(String(format: "%.4f\t%.4f\t%@", 1.0 - l.y, l.x, l.text))
}
