import SwiftUI
import VisionKit

private let PI_BASE = URL(string: "http://192.168.1.50:8080")! // change me

@MainActor
final class CheckpointModel: ObservableObject {
    @Published var zone: Int?
    @Published var message = "Scan the QR code nearest to you"
    @Published var moving = false

    func accept(_ payload: String) {
        guard payload.hasPrefix("FETCH:"),
              let id = Int(payload.dropFirst("FETCH:".count)) else { return }
        zone = id
        message = "Checkpoint \(id) selected"
    }

    func summon() async {
        guard let zone else { return }
        var request = URLRequest(url: PI_BASE.appendingPathComponent("come"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(["zone": zone])
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 202 else {
                throw URLError(.badServerResponse)
            }
            moving = true
            message = "FETCH is coming to checkpoint \(zone)"
        } catch {
            message = "Could not contact FETCH: \(error.localizedDescription)"
        }
    }

    func cancel() async {
        var request = URLRequest(url: PI_BASE.appendingPathComponent("cancel"))
        request.httpMethod = "POST"
        _ = try? await URLSession.shared.data(for: request)
        moving = false
        message = "Cancelled"
    }
}

struct BarcodeScanner: UIViewControllerRepresentable {
    let onCode: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onCode) }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.qr])],
            qualityLevel: .balanced,
            recognizesMultipleItems: false,
            isHighFrameRateTrackingEnabled: false,
            isPinchToZoomEnabled: true,
            isGuidanceEnabled: true,
            isHighlightingEnabled: true)
        scanner.delegate = context.coordinator
        try? scanner.startScanning()
        return scanner
    }

    func updateUIViewController(_ controller: DataScannerViewController, context: Context) {}

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let onCode: (String) -> Void
        init(_ onCode: @escaping (String) -> Void) { self.onCode = onCode }
        func dataScanner(_ scanner: DataScannerViewController,
                         didAdd addedItems: [RecognizedItem],
                         allItems: [RecognizedItem]) {
            for item in addedItems {
                if case .barcode(let code) = item, let value = code.payloadStringValue {
                    onCode(value)
                }
            }
        }
    }
}

struct FetchCheckpointView: View {
    @StateObject private var model = CheckpointModel()

    var body: some View {
        VStack(spacing: 18) {
            BarcodeScanner { model.accept($0) }
                .clipShape(RoundedRectangle(cornerRadius: 18))
            Text(model.message).multilineTextAlignment(.center)
            Button(model.moving ? "STOP" : "CALL FETCH") {
                Task { model.moving ? await model.cancel() : await model.summon() }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(model.zone == nil && !model.moving)
        }
        .padding()
    }
}
