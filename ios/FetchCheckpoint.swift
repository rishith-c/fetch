import Foundation
import SwiftUI
import VisionKit

private struct FetchStatus: Decodable {
    let state: String
    let goal: Int?
    let at: Int?
    let navigationState: String
    let sonarCm: [Int]
    let estop: Bool
    let telemetryFresh: Bool
    let cameraFresh: Bool
    let error: String?

    enum CodingKeys: String, CodingKey {
        case state, goal, at, estop, error
        case navigationState = "navigation_state"
        case sonarCm = "sonar_cm"
        case telemetryFresh = "telemetry_fresh"
        case cameraFresh = "camera_fresh"
    }
}

private struct APIError: Decodable {
    let error: String
}

@MainActor
final class CheckpointModel: ObservableObject {
    @Published var checkpoint: Int?
    @Published var message = "Scan the FETCH checkpoint nearest you"
    @Published var moving = false
    @Published var serverAddress: String {
        didSet { UserDefaults.standard.set(serverAddress, forKey: "fetchServer") }
    }

    private var monitorTask: Task<Void, Never>?

    init() {
        serverAddress = UserDefaults.standard.string(forKey: "fetchServer")
            ?? "http://fetch.local:8080"
    }

    deinit {
        monitorTask?.cancel()
    }

    private var baseURL: URL? {
        let value = serverAddress.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: value),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              url.host != nil else { return nil }
        return url
    }

    func accept(_ payload: String) {
        let cleaned = payload.trimmingCharacters(in: .whitespacesAndNewlines)
        guard cleaned.hasPrefix("FETCH:"),
              let value = Int(cleaned.dropFirst("FETCH:".count)),
              value >= 0 else {
            message = "That is not a FETCH checkpoint QR code"
            return
        }
        checkpoint = value
        message = "Checkpoint \(value) selected"
    }

    private func request(path: String, method: String = "GET", body: Data? = nil) async throws
        -> (Data, HTTPURLResponse) {
        guard let baseURL else { throw URLError(.badURL) }
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = method
        request.timeoutInterval = 2.0
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        guard 200..<300 ~= http.statusCode else {
            if let apiError = try? JSONDecoder().decode(APIError.self, from: data) {
                throw NSError(domain: "FETCH", code: http.statusCode,
                              userInfo: [NSLocalizedDescriptionKey: apiError.error])
            }
            throw URLError(.badServerResponse)
        }
        return (data, http)
    }

    func testConnection() async {
        do {
            let (data, _) = try await request(path: "status")
            let status = try JSONDecoder().decode(FetchStatus.self, from: data)
            message = status.cameraFresh && status.telemetryFresh
                ? "FETCH is connected and ready"
                : "Connected, but camera or motor telemetry is not ready"
        } catch {
            message = "Cannot reach FETCH: \(error.localizedDescription)"
        }
    }

    func summon() async {
        guard let checkpoint else {
            message = "Scan your nearest checkpoint first"
            return
        }
        do {
            let body = try JSONEncoder().encode(["zone": checkpoint])
            _ = try await request(path: "come", method: "POST", body: body)
            moving = true
            message = "FETCH is coming to checkpoint \(checkpoint)"
            startMonitoring()
        } catch {
            moving = false
            message = "FETCH could not start: \(error.localizedDescription)"
        }
    }

    func cancel() async {
        monitorTask?.cancel()
        monitorTask = nil
        do {
            _ = try await request(path: "cancel", method: "POST", body: Data("{}".utf8))
            message = "FETCH stopped"
        } catch {
            message = "Stop request failed—use the physical power switch"
        }
        moving = false
    }

    private func startMonitoring() {
        monitorTask?.cancel()
        monitorTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                do {
                    let (data, _) = try await self.request(path: "status")
                    let status = try JSONDecoder().decode(FetchStatus.self, from: data)
                    switch status.state {
                    case "ARRIVED":
                        self.moving = false
                        self.message = "FETCH arrived at checkpoint \(status.at ?? status.goal ?? 0)"
                        return
                    case "FAILED":
                        self.moving = false
                        self.message = "FETCH stopped: \(status.error ?? "route failed")"
                        return
                    case "ROUTING":
                        self.message = "FETCH: \(status.navigationState.lowercased())"
                    default:
                        self.moving = false
                        return
                    }
                } catch {
                    // The Pi independently stops after two seconds without this
                    // heartbeat. Keep retrying briefly so transient Wi-Fi does not
                    // immediately replace the useful on-screen state.
                    self.message = "Connection lost—FETCH is stopping automatically"
                }
                try? await Task.sleep(for: .milliseconds(500))
            }
        }
    }
}

struct BarcodeScanner: UIViewControllerRepresentable {
    let onCode: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onCode: onCode) }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.qr])],
            qualityLevel: .balanced,
            recognizesMultipleItems: false,
            isHighFrameRateTrackingEnabled: false,
            isPinchToZoomEnabled: true,
            isGuidanceEnabled: true,
            isHighlightingEnabled: true
        )
        scanner.delegate = context.coordinator
        try? scanner.startScanning()
        return scanner
    }

    func updateUIViewController(_ controller: DataScannerViewController, context: Context) {
        if !controller.isScanning { try? controller.startScanning() }
    }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let onCode: (String) -> Void
        init(onCode: @escaping (String) -> Void) { self.onCode = onCode }

        func dataScanner(_ dataScanner: DataScannerViewController,
                         didAdd addedItems: [RecognizedItem],
                         allItems: [RecognizedItem]) {
            for item in addedItems {
                if case let .barcode(code) = item,
                   let payload = code.payloadStringValue {
                    onCode(payload)
                    return
                }
            }
        }
    }
}

struct ContentView: View {
    @StateObject private var model = CheckpointModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                if DataScannerViewController.isSupported &&
                    DataScannerViewController.isAvailable {
                    BarcodeScanner(onCode: model.accept)
                        .frame(height: 320)
                        .clipShape(RoundedRectangle(cornerRadius: 18))
                } else {
                    ContentUnavailableView("Camera scanner unavailable",
                                           systemImage: "qrcode.viewfinder")
                }

                Text(model.message)
                    .multilineTextAlignment(.center)

                TextField("http://fetch.local:8080", text: $model.serverAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                    .textFieldStyle(.roundedBorder)

                Button("TEST CONNECTION") {
                    Task { await model.testConnection() }
                }
                .buttonStyle(.bordered)

                if model.moving {
                    Button("STOP FETCH", role: .destructive) {
                        Task { await model.cancel() }
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    Button("CALL FETCH") {
                        Task { await model.summon() }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.checkpoint == nil)
                }
            }
            .padding()
            .navigationTitle("FETCH")
        }
    }
}

@main
struct FetchCheckpointApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}
