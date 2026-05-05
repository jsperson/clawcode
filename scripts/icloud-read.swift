#!/usr/bin/env swift
// Reads an iCloud file using NSFileCoordinator to avoid deadlocks.
// Usage: swift icloud-read.swift <path> [output-path]
// If output-path is omitted, writes to stdout.

import Foundation

guard CommandLine.arguments.count >= 2 else {
    FileHandle.standardError.write("Usage: icloud-read <path> [output-path]\n".data(using: .utf8)!)
    exit(1)
}

let inputPath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: inputPath)
var coordError: NSError?
let coordinator = NSFileCoordinator()
var readData: Data?

coordinator.coordinate(readingItemAt: url, options: [], error: &coordError) { newURL in
    readData = try? Data(contentsOf: newURL)
}

if let error = coordError {
    FileHandle.standardError.write("Coordination error: \(error.localizedDescription)\n".data(using: .utf8)!)
    exit(1)
}

guard let data = readData else {
    FileHandle.standardError.write("Failed to read file\n".data(using: .utf8)!)
    exit(1)
}

if CommandLine.arguments.count >= 3 {
    let outputPath = CommandLine.arguments[2]
    do {
        try data.write(to: URL(fileURLWithPath: outputPath))
    } catch {
        FileHandle.standardError.write("Write error: \(error.localizedDescription)\n".data(using: .utf8)!)
        exit(1)
    }
} else {
    FileHandle.standardOutput.write(data)
}
