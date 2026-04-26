import Vision
import Foundation
import Cocoa

guard CommandLine.arguments.count > 1 else {
    print("[]")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("[]")
    exit(1)
}

// cgImage width/height
let width = CGFloat(cgImage.width)
let height = CGFloat(cgImage.height)

let requestHandler = VNImageRequestHandler(cgImage: cgImage, options: [:])
let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        print("[]")
        return
    }
    
    var boxes: [[Int]] = []
    
    for observation in observations {
        guard let topCandidate = observation.topCandidates(1).first else { continue }
        let text = topCandidate.string.uppercased()
        
        // Match PROCER with fuzzy logic like PaddleOCR
        if text.contains("PROCER") || text.contains("PROCE") || text.contains("OCER") || text.contains("R0CER") {
            let boundingBox = observation.boundingBox
            // VN uses lower-left origin. boundingBox is normalized 0-1
            let xMin = Int(boundingBox.minX * 1000)
            let xMax = Int(boundingBox.maxX * 1000)
            let yMax = Int((1.0 - boundingBox.minY) * 1000)
            let yMin = Int((1.0 - boundingBox.maxY) * 1000)
            
            boxes.append([yMin, xMin, yMax, xMax])
        }
    }
    
    if let json = try? JSONSerialization.data(withJSONObject: boxes, options: []) {
        if let string = String(data: json, encoding: .utf8) {
            print(string)
        }
    }
}

request.recognitionLevel = .accurate
try? requestHandler.perform([request])
