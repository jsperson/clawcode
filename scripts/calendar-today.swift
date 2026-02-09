#!/usr/bin/env swift
// Outputs today's calendar events as JSON using EventKit.
// Does NOT require Full Disk Access — only Calendar permission.

import EventKit
import Foundation

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)

store.requestFullAccessToEvents { granted, error in
    guard granted else {
        let msg = error?.localizedDescription ?? "Calendar access denied"
        fputs("Error: \(msg)\n", stderr)
        print("[]")
        semaphore.signal()
        return
    }

    let cal = Calendar.current
    let start = cal.startOfDay(for: Date())
    let end = cal.date(byAdding: .day, value: 1, to: start)!
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
    let events = store.events(matching: predicate)

    var results: [[String: Any]] = []
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss Z"

    for event in events {
        if event.calendar.title == "Found in Natural Language" { continue }
        var dict: [String: Any] = [
            "title": event.title ?? "",
            "calendar": event.calendar.title ?? "",
            "allDay": event.isAllDay,
            "sctime": formatter.string(from: event.startDate),
            "ectime": formatter.string(from: event.endDate),
        ]
        if let loc = event.location, !loc.isEmpty {
            dict["location"] = loc
        }
        if let notes = event.notes, !notes.isEmpty {
            dict["notes"] = notes
        }
        results.append(dict)
    }

    if let data = try? JSONSerialization.data(withJSONObject: results, options: [.sortedKeys]),
       let json = String(data: data, encoding: .utf8) {
        print(json)
    } else {
        print("[]")
    }
    semaphore.signal()
}

semaphore.wait()
