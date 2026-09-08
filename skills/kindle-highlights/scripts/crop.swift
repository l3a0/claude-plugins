import Foundation
import AppKit
// Usage: crop <in.png> <x0> <y0> <x1> <y1> <out.png> [scale] [pad]  (normalized coords, top-left origin; pad in source px, default 40).
// Prints JSON with the crop's pixel origin/size, scale and the source size, so callers can map crop coords back to the page.
let a = CommandLine.arguments
guard a.count >= 7, let img = NSImage(contentsOfFile: a[1]), let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff), let cg = rep.cgImage else { FileHandle.standardError.write("usage/load error\n".data(using: .utf8)!); exit(1) }
let scale: CGFloat = a.count >= 8 ? CGFloat(Double(a[7]) ?? 1.0) : 1.0
let pad: CGFloat = a.count >= 9 ? CGFloat(Double(a[8]) ?? 40.0) : 40.0
let W = CGFloat(cg.width), H = CGFloat(cg.height)
let x0 = max(0, floor(CGFloat(Double(a[2])!) * W - pad)), y0 = max(0, floor(CGFloat(Double(a[3])!) * H - pad))
let x1 = min(W, ceil(CGFloat(Double(a[4])!) * W + pad)), y1 = min(H, ceil(CGFloat(Double(a[5])!) * H + pad))
guard let sub = cg.cropping(to: CGRect(x: x0, y: y0, width: x1 - x0, height: y1 - y0)) else { exit(2) }
let ow = Int((x1 - x0) * scale), oh = Int((y1 - y0) * scale)
let cs = CGColorSpaceCreateDeviceRGB()
guard let ctx = CGContext(data: nil, width: ow, height: oh, bitsPerComponent: 8, bytesPerRow: 0, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(4) }
ctx.interpolationQuality = .high
ctx.draw(sub, in: CGRect(x: 0, y: 0, width: ow, height: oh))
guard let out = ctx.makeImage() else { exit(5) }
let outRep = NSBitmapImageRep(cgImage: out)
guard let data = outRep.representation(using: .png, properties: [:]) else { exit(3) }
try! data.write(to: URL(fileURLWithPath: a[6]))
print("{\"x0\":\(Int(x0)),\"y0\":\(Int(y0)),\"w\":\(Int(x1 - x0)),\"h\":\(Int(y1 - y0)),\"scale\":\(scale),\"W\":\(Int(W)),\"H\":\(Int(H))}")
