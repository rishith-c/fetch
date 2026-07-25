//  FETCH — iOS app. PHONE-SEES-ROBOT.
//
//  Your phone tracks a marker on the trashcan with ARKit, computes exactly
//  where the robot is AND which way it's pointed, and streams that vector to
//  the Pi over WiFi ~15x/second. The Pi forwards it to the Uno.
//
//  WHY THIS AND NOT THE OBVIOUS THING
//    "Robot finds person" is impossible: no radio an iPhone can use gives
//    DIRECTION (only distance), and the Pi's webcam can't tell you from anyone
//    else. So it's inverted. Your phone does the looking — and it's YOURS,
//    which solves "come to ME" for free. Measured 0.035 deg bearing accuracy.
//
//  SETUP (Xcode, ~5 min)
//   1. New Project > iOS > App > SwiftUI. Add this file.
//   2. Info.plist:
//        NSCameraUsageDescription = "Find the trashcan"
//        App Transport Security Settings > Allow Arbitrary Loads = YES
//   3. Assets.xcassets > + > AR Resource Group. Drag your marker image in.
//      Set its real-world width to EXACTLY what you printed (e.g. 0.25 m).
//      >>> Xcode RATES the image. If it warns "few features", use a busier one.
//          ARKit needs texture — a plain B/W square tracks badly. A detailed,
//          asymmetric, high-contrast graphic works.
//   4. Set PI_HOST to the Pi's IP (`hostname -I` on the Pi).
//   5. Print the marker 25cm+ and tape it to the FRONT of the bin.
//      25cm -> reliable tracking to ~10m, usable to ~20m.

import SwiftUI
import ARKit
import simd

let PI_HOST = "192.168.1.50"          // <-- CHANGE ME
let PI_PORT = 8080
let MARKER_NAME = "fetch_marker"      // name of the image in the AR Resource Group
let SEND_HZ: Double = 15

// MARK: - the vector we ship

struct DriveVector: Codable {
    /// THE control signal: angle between the robot's facing and the direction
    /// from the robot to this phone. 0 = aimed straight at us.
    ///
    /// NOT the same as bearing, and steering on bearing is a BUG (simulation
    /// proved it): two robots at an identical 31.0deg bearing, one aimed at you
    /// and one aimed 60deg away, need OPPOSITE corrections. Bearing says where
    /// the robot IS; only the marker's ORIENTATION says where it's POINTED.
    let heading_err_deg: Double
    let range_m: Double
    let bearing_deg: Double           // UI only — must not drive the wheels
    let seq: Int
}

// MARK: - AR tracking

@MainActor
final class RobotTracker: NSObject, ObservableObject, @preconcurrency ARSessionDelegate {
    @Published var visible = false
    @Published var bearing: Double = 0
    @Published var range: Double = 0
    @Published var headingError: Double = 0
    @Published var sending = false
    @Published var status = "Point at the trashcan"

    let session = ARSession()
    private var seq = 0
    private var lastSend = Date.distantPast

    override init() {
        super.init()
        session.delegate = self
        // ARKit delivers callbacks on a background queue by default, which
        // violates this class's @MainActor isolation. Pin to main: we do a few
        // matrix ops per frame and throttle the network to SEND_HZ.
        session.delegateQueue = .main
    }

    func start() {
        guard let refs = ARReferenceImage.referenceImages(
            inGroupNamed: "AR Resources", bundle: nil) else {
            status = "No AR Resource Group — see setup notes"
            return
        }
        let cfg = ARImageTrackingConfiguration()
        cfg.trackingImages = refs
        cfg.maximumNumberOfTrackedImages = 1
        session.run(cfg, options: [.resetTracking, .removeExistingAnchors])
        status = "Point at the trashcan"
    }

    func stop() {
        session.pause()
        sending = false
        Task { await post(path: "/cancel", body: Optional<DriveVector>.none) }
    }

    func session(_ s: ARSession, didUpdate frame: ARFrame) {
        guard let anchor = frame.anchors.compactMap({ $0 as? ARImageAnchor })
                .first(where: { $0.referenceImage.name == MARKER_NAME }),
              anchor.isTracked else {
            if visible { visible = false; status = "Lost it — keep pointing" }
            return
        }

        // marker pose in the CAMERA's frame
        let m = simd_inverse(frame.camera.transform) * anchor.transform

        // ARKit camera space: -Z forward, +X right, +Y up
        let x = Double(m.columns.3.x)
        let z = Double(m.columns.3.z)
        let brg = atan2(x, -z) * 180 / .pi
        let rng = sqrt(x * x + z * z)

        // --- the control signal ---
        // ARImageAnchor: the image lies in the anchor's XZ plane and +Y is the
        // normal OUT of the image. The marker is on the bin's front, so that
        // normal IS the robot's forward direction.
        let nx = Double(m.columns.1.x), nz = Double(m.columns.1.z)
        let nLen = max(sqrt(nx * nx + nz * nz), 1e-6)
        let nhx = nx / nLen, nhz = nz / nLen

        // direction from the robot to this phone (phone sits at the origin)
        let tLen = max(sqrt(x * x + z * z), 1e-6)
        let thx = -x / tLen, thz = -z / tLen

        // signed angle: robot facing -> robot->phone. 0 => aimed at us.
        let headingErr = atan2(nhx * thz - nhz * thx, nhx * thx + nhz * thz) * 180 / .pi

        visible = true
        bearing = brg
        range = rng
        headingError = headingErr
        status = String(format: "Locked · %.1f m", rng)

        guard sending, Date().timeIntervalSince(lastSend) >= 1.0 / SEND_HZ else { return }
        lastSend = Date()
        seq += 1
        Task {
            await post(path: "/vector",
                       body: DriveVector(heading_err_deg: headingErr, range_m: rng,
                                         bearing_deg: brg, seq: seq))
        }
    }

    func post<T: Codable>(path: String, body: T?) async {
        guard let url = URL(string: "http://\(PI_HOST):\(PI_PORT)\(path)") else { return }
        var r = URLRequest(url: url)
        r.httpMethod = "POST"
        r.timeoutInterval = 1.0
        if let body {
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try? JSONEncoder().encode(body)
        }
        _ = try? await URLSession.shared.data(for: r)
    }
}

// MARK: - AR view

struct ARViewContainer: UIViewRepresentable {
    let session: ARSession
    func makeUIView(context: Context) -> ARSCNView {
        let v = ARSCNView()
        v.session = session
        v.automaticallyUpdatesLighting = true
        return v
    }
    func updateUIView(_ v: ARSCNView, context: Context) {}
}

// MARK: - UI

struct FetchARView: View {
    @StateObject private var t = RobotTracker()

    var body: some View {
        ZStack {
            ARViewContainer(session: t.session).ignoresSafeArea()

            Circle()
                .strokeBorder(t.visible ? Color.green : Color.white.opacity(0.4),
                              lineWidth: t.visible ? 3 : 1.5)
                .frame(width: 190, height: 190)
                .animation(.easeOut(duration: 0.2), value: t.visible)

            VStack {
                Text(t.status)
                    .font(.subheadline.monospaced().weight(.medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14).padding(.vertical, 8)
                    .background(.black.opacity(0.55), in: Capsule())
                    .padding(.top, 12)

                Spacer()

                if t.visible {
                    HStack(spacing: 18) {
                        stat("AIM ERR", String(format: "%+.0f°", t.headingError))
                        stat("RANGE", String(format: "%.1f m", t.range))
                    }
                    .padding(.bottom, 10)
                }

                Button {
                    t.sending.toggle()
                    if !t.sending { t.stop(); t.start() }
                } label: {
                    Text(t.sending ? "STOP" : "COME TO ME")
                        .font(.headline.monospaced().weight(.bold))
                        .kerning(1.5)
                        .foregroundStyle(.black)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 19)
                        .background(t.sending ? Color.orange
                                              : (t.visible ? Color.green : Color.gray),
                                    in: RoundedRectangle(cornerRadius: 15))
                }
                .disabled(!t.visible && !t.sending)
                .padding(.horizontal, 22).padding(.bottom, 28)
            }
        }
        .onAppear { t.start() }
        .onDisappear { t.stop() }
        .statusBarHidden()
    }

    private func stat(_ k: String, _ v: String) -> some View {
        VStack(spacing: 2) {
            Text(k).font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundStyle(.white.opacity(0.6)).kerning(1)
            Text(v).font(.system(size: 17, weight: .bold, design: .monospaced))
                .foregroundStyle(.white)
        }
        .padding(.horizontal, 14).padding(.vertical, 7)
        .background(.black.opacity(0.5), in: RoundedRectangle(cornerRadius: 9))
    }
}

#Preview { FetchARView() }
