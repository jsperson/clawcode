#!/usr/bin/env swift
// clawcal — macOS Calendar CLI using EventKit
// Compiled at install time: swiftc -O scripts/clawcal.swift -o bin/clawcal

import EventKit
import Foundation

// MARK: - Helpers

let dateFormatter: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "yyyy-MM-dd"
    f.locale = Locale(identifier: "en_US_POSIX")
    return f
}()

let timeFormatter: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "HH:mm"
    f.locale = Locale(identifier: "en_US_POSIX")
    return f
}()

func jsonOutput(_ value: Any) {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

func errorExit(_ message: String) -> Never {
    let err: [String: Any] = ["error": message]
    if let data = try? JSONSerialization.data(withJSONObject: err),
       let str = String(data: data, encoding: .utf8) {
        FileHandle.standardError.write(str.data(using: .utf8)!)
        FileHandle.standardError.write("\n".data(using: .utf8)!)
    }
    exit(1)
}

// MARK: - Date Parsing

func parseDate(_ str: String) -> Date? {
    let cal = Calendar.current
    let today = cal.startOfDay(for: Date())

    switch str.lowercased() {
    case "today":
        return today
    case "tomorrow":
        return cal.date(byAdding: .day, value: 1, to: today)
    case "yesterday":
        return cal.date(byAdding: .day, value: -1, to: today)
    case "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday":
        return nextWeekday(str.lowercased(), from: today)
    default:
        // +Ndays / -Ndays
        if let match = str.range(of: #"^([+-])(\d+)days$"#, options: .regularExpression) {
            let s = str[match]
            let sign = s.hasPrefix("+") ? 1 : -1
            let numStr = str.dropFirst(1).dropLast(4)
            if let n = Int(numStr) {
                return cal.date(byAdding: .day, value: sign * n, to: today)
            }
        }
        // YYYY-MM-DD
        return dateFormatter.date(from: str)
    }
}

func nextWeekday(_ name: String, from date: Date) -> Date? {
    let map = ["sunday": 1, "monday": 2, "tuesday": 3, "wednesday": 4,
               "thursday": 5, "friday": 6, "saturday": 7]
    guard let target = map[name] else { return nil }
    let cal = Calendar.current
    let current = cal.component(.weekday, from: date)
    var delta = target - current
    if delta <= 0 { delta += 7 }
    return cal.date(byAdding: .day, value: delta, to: date)
}

func parseTime(_ str: String, on date: Date) -> Date? {
    let parts = str.split(separator: ":")
    guard parts.count == 2, let h = Int(parts[0]), let m = Int(parts[1]) else { return nil }
    return Calendar.current.date(bySettingHour: h, minute: m, second: 0, of: date)
}

// MARK: - EventKit Access

func requestAccess(store: EKEventStore) -> Bool {
    var granted = false
    var done = false

    if #available(macOS 14.0, *) {
        store.requestFullAccessToEvents { g, _ in
            granted = g
            done = true
        }
    } else {
        store.requestAccess(to: .event) { g, _ in
            granted = g
            done = true
        }
    }

    // Run the main run loop so the macOS TCC prompt can appear
    while !done {
        RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))
    }
    return granted
}

// MARK: - Commands

func listCalendars(store: EKEventStore) {
    let calendars = store.calendars(for: .event)
    let result = calendars.map { cal -> [String: Any] in
        return [
            "name": cal.title,
            "type": String(describing: cal.type.rawValue),
            "source": cal.source?.title ?? "",
            "color": cal.cgColor != nil ? "#" + hexColor(cal.cgColor!) : "",
        ]
    }.sorted { ($0["name"] as? String ?? "") < ($1["name"] as? String ?? "") }
    jsonOutput(result)
}

func hexColor(_ cgColor: CGColor) -> String {
    guard let components = cgColor.components, components.count >= 3 else { return "000000" }
    let r = Int(components[0] * 255)
    let g = Int(components[1] * 255)
    let b = Int(components[2] * 255)
    return String(format: "%02x%02x%02x", r, g, b)
}

func listEvents(store: EKEventStore, from startDate: Date, to endDate: Date,
                calendars filterCals: [String]?, exclude excludeCals: [String]?) {
    var ekCalendars: [EKCalendar]? = nil

    if let filterCals = filterCals, !filterCals.isEmpty {
        let all = store.calendars(for: .event)
        let lowered = Set(filterCals.map { $0.lowercased() })
        ekCalendars = all.filter { lowered.contains($0.title.lowercased()) }
        if ekCalendars!.isEmpty {
            jsonOutput([Any]())
            return
        }
    }

    let predicate = store.predicateForEvents(withStart: startDate, end: endDate, calendars: ekCalendars)
    var events = store.events(matching: predicate)

    if let excludeCals = excludeCals, !excludeCals.isEmpty {
        let lowered = Set(excludeCals.map { $0.lowercased() })
        events = events.filter { !lowered.contains($0.calendar.title.lowercased()) }
    }

    events.sort { $0.startDate < $1.startDate }

    let result: [[String: Any]] = events.map { ev in
        var dict: [String: Any] = [
            "title": ev.title ?? "",
            "calendar": ev.calendar.title,
            "all_day": ev.isAllDay,
            "location": ev.location ?? "",
            "date": dateFormatter.string(from: ev.startDate),
        ]
        if ev.isAllDay {
            dict["start"] = ""
            dict["end"] = ""
            if let endDate = ev.endDate {
                let endDay = Calendar.current.date(byAdding: .day, value: -1, to: endDate) ?? endDate
                // Only include end_date for multi-day events (endDay after startDate)
                if endDay > ev.startDate {
                    dict["end_date"] = dateFormatter.string(from: endDay)
                }
            }
        } else {
            dict["start"] = timeFormatter.string(from: ev.startDate)
            dict["end"] = ev.endDate != nil ? timeFormatter.string(from: ev.endDate) : ""
        }
        if let notes = ev.notes, !notes.isEmpty {
            dict["notes"] = notes
        }
        if let url = ev.url {
            dict["url"] = url.absoluteString
        }
        return dict
    }
    jsonOutput(result)
}

func addEvent(store: EKEventStore, title: String, date: Date, startTime: String?,
              endTime: String?, endDate: String?, allDay: Bool,
              calendarName: String?, location: String?, notes: String?) {
    let event = EKEvent(eventStore: store)
    event.title = title

    if allDay || (startTime == nil && endDate != nil) {
        event.isAllDay = true
        event.startDate = Calendar.current.startOfDay(for: date)
        if let endDateStr = endDate, let ed = parseDate(endDateStr) {
            // EventKit all-day end is exclusive, so add 1 day
            event.endDate = Calendar.current.date(byAdding: .day, value: 1, to: Calendar.current.startOfDay(for: ed))
        } else {
            event.endDate = Calendar.current.date(byAdding: .day, value: 1, to: event.startDate)
        }
    } else {
        guard let startStr = startTime, let start = parseTime(startStr, on: date) else {
            errorExit("--start is required for non-all-day events")
        }
        event.startDate = start
        if let endStr = endTime, let end = parseTime(endStr, on: date) {
            event.endDate = end
        } else {
            // Default: 1 hour
            event.endDate = Calendar.current.date(byAdding: .hour, value: 1, to: start)
        }
    }

    if let calendarName = calendarName {
        let all = store.calendars(for: .event)
        if let cal = all.first(where: { $0.title.lowercased() == calendarName.lowercased() }) {
            event.calendar = cal
        } else {
            errorExit("Calendar '\(calendarName)' not found")
        }
    } else {
        event.calendar = store.defaultCalendarForNewEvents
    }

    if let location = location { event.location = location }
    if let notes = notes { event.notes = notes }

    do {
        try store.save(event, span: .thisEvent)
    } catch {
        errorExit("Failed to save event: \(error.localizedDescription)")
    }

    var result: [String: Any] = [
        "created": true,
        "title": event.title!,
        "date": dateFormatter.string(from: event.startDate),
        "calendar": event.calendar.title,
        "all_day": event.isAllDay,
    ]
    if !event.isAllDay {
        result["start"] = timeFormatter.string(from: event.startDate)
        result["end"] = timeFormatter.string(from: event.endDate)
    }
    jsonOutput(result)
}

// MARK: - Argument Parsing

func getArg(_ args: [String], flag: String) -> String? {
    guard let idx = args.firstIndex(of: flag), idx + 1 < args.count else { return nil }
    return args[idx + 1]
}

func hasFlag(_ args: [String], _ flag: String) -> Bool {
    return args.contains(flag)
}

// MARK: - Main

let args = Array(CommandLine.arguments.dropFirst())

guard let subcommand = args.first else {
    errorExit("Usage: clawcal <events|add|calendars> [options]")
}

let store = EKEventStore()

guard requestAccess(store: store) else {
    errorExit("Calendar access denied. Grant access in System Settings > Privacy & Security > Calendars")
}

switch subcommand {
case "calendars":
    listCalendars(store: store)

case "events":
    let cal = Calendar.current
    let today = cal.startOfDay(for: Date())

    var startDate = today
    var endDate = cal.date(byAdding: .day, value: 1, to: today)!

    if let days = getArg(args, flag: "--days"), let n = Int(days) {
        endDate = cal.date(byAdding: .day, value: n, to: today)!
    }
    if let fromStr = getArg(args, flag: "--from"), let d = parseDate(fromStr) {
        startDate = cal.startOfDay(for: d)
        // If no --to and no --days, default to end of --from day
        if getArg(args, flag: "--to") == nil && getArg(args, flag: "--days") == nil {
            endDate = cal.date(byAdding: .day, value: 1, to: startDate)!
        }
    }
    if let toStr = getArg(args, flag: "--to"), let d = parseDate(toStr) {
        endDate = cal.date(byAdding: .day, value: 1, to: cal.startOfDay(for: d))!
    }

    let filterCals = getArg(args, flag: "--calendars")?.split(separator: ",").map(String.init)
    let excludeCals = getArg(args, flag: "--exclude")?.split(separator: ",").map(String.init)

    listEvents(store: store, from: startDate, to: endDate, calendars: filterCals, exclude: excludeCals)

case "add":
    guard args.count >= 2 else {
        errorExit("Usage: clawcal add \"Title\" --date YYYY-MM-DD --start HH:MM --end HH:MM [--calendar Name] [--location ...] [--notes ...]")
    }
    let title = args[1]

    guard let dateStr = getArg(args, flag: "--date"), let date = parseDate(dateStr) else {
        errorExit("--date is required (e.g. --date 2026-03-15 or --date tomorrow)")
    }

    let allDay = hasFlag(args, "--all-day")
    let startTime = getArg(args, flag: "--start")
    let endTime = getArg(args, flag: "--end")
    let endDateStr = getArg(args, flag: "--end-date")
    let calendarName = getArg(args, flag: "--calendar")
    let location = getArg(args, flag: "--location")
    let notes = getArg(args, flag: "--notes")

    addEvent(store: store, title: title, date: date, startTime: startTime,
             endTime: endTime, endDate: endDateStr, allDay: allDay,
             calendarName: calendarName, location: location, notes: notes)

default:
    errorExit("Unknown command: \(subcommand). Use: events, add, calendars")
}
