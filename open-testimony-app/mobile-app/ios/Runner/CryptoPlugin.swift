import Flutter
import UIKit
import Security
import CryptoKit
import CommonCrypto
import AVFoundation
import CoreLocation

/// Platform channel plugin for hardware-backed ECDSA signing using Secure Enclave.
class CryptoPlugin: NSObject, FlutterPlugin {
    private static let keyTag = "com.opentestimony.signing-key"

    static func register(with registrar: FlutterPluginRegistrar) {
        let channel = FlutterMethodChannel(
            name: "com.opentestimony/crypto",
            binaryMessenger: registrar.messenger()
        )
        let instance = CryptoPlugin()
        registrar.addMethodCallDelegate(instance, channel: channel)
    }

    func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "isHardwareBacked":
            result(SecureEnclave.isAvailable)

        case "generateKey":
            generateKey(result: result)

        case "getPublicKey":
            getPublicKey(result: result)

        case "sign":
            guard let args = call.arguments as? [String: Any],
                  let data = args["data"] as? String else {
                result(FlutterError(code: "INVALID_ARGS", message: "Missing 'data' argument", details: nil))
                return
            }
            sign(data: data, result: result)

        case "extractVideoLocation":
            guard let args = call.arguments as? [String: Any],
                  let path = args["path"] as? String else {
                result(FlutterError(code: "INVALID_ARGS", message: "Missing 'path' argument", details: nil))
                return
            }
            extractVideoLocation(path: path, result: result)

        default:
            result(FlutterMethodNotImplemented)
        }
    }

    private func generateKey(result: @escaping FlutterResult) {
        // Delete existing key if any
        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: CryptoPlugin.keyTag,
        ]
        SecItemDelete(deleteQuery as CFDictionary)

        // Create access control for Secure Enclave
        guard let access = SecAccessControlCreateWithFlags(
            kCFAllocatorDefault,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            .privateKeyUsage,
            nil
        ) else {
            result(FlutterError(code: "ACCESS_CONTROL", message: "Failed to create access control", details: nil))
            return
        }

        let attributes: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String: 256,
            kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
            kSecPrivateKeyAttrs as String: [
                kSecAttrIsPermanent as String: true,
                kSecAttrApplicationTag as String: CryptoPlugin.keyTag,
                kSecAttrAccessControl as String: access,
            ],
        ]

        var error: Unmanaged<CFError>?
        guard SecKeyCreateRandomKey(attributes as CFDictionary, &error) != nil else {
            let errMsg = error?.takeRetainedValue().localizedDescription ?? "Unknown error"
            result(FlutterError(code: "KEY_GEN", message: "Key generation failed: \(errMsg)", details: nil))
            return
        }

        result(true)
    }

    private func getPrivateKey() -> SecKey? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: CryptoPlugin.keyTag,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecReturnRef as String: true,
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess else { return nil }
        return (item as! SecKey)
    }

    private func getPublicKey(result: @escaping FlutterResult) {
        guard let privateKey = getPrivateKey(),
              let publicKey = SecKeyCopyPublicKey(privateKey) else {
            result(FlutterError(code: "NO_KEY", message: "Key not found", details: nil))
            return
        }

        var error: Unmanaged<CFError>?
        guard let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, &error) as Data? else {
            result(FlutterError(code: "EXPORT", message: "Failed to export public key", details: nil))
            return
        }

        // SecKeyCopyExternalRepresentation returns raw EC point (04 || x || y).
        // Wrap in SPKI (SubjectPublicKeyInfo) ASN.1 structure for standard PEM format.
        let spkiHeader: [UInt8] = [
            0x30, 0x59,       // SEQUENCE (89 bytes total)
            0x30, 0x13,       //   SEQUENCE (19 bytes) - AlgorithmIdentifier
            0x06, 0x07,       //     OID (7 bytes) - id-ecPublicKey
            0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01,
            0x06, 0x08,       //     OID (8 bytes) - prime256v1 (P-256)
            0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07,
            0x03, 0x42,       //   BIT STRING (66 bytes)
            0x00              //     0 unused bits
        ]
        var spkiData = Data(spkiHeader)
        spkiData.append(publicKeyData)

        let base64Key = spkiData.base64EncodedString(options: [.lineLength64Characters, .endLineWithLineFeed])
        let pem = "-----BEGIN PUBLIC KEY-----\n\(base64Key)\n-----END PUBLIC KEY-----"
        result(pem)
    }

    private func sign(data: String, result: @escaping FlutterResult) {
        guard let privateKey = getPrivateKey() else {
            result(FlutterError(code: "NO_KEY", message: "Signing key not found", details: nil))
            return
        }

        guard let dataBytes = data.data(using: .utf8) else {
            result(FlutterError(code: "ENCODING", message: "Failed to encode data", details: nil))
            return
        }

        var error: Unmanaged<CFError>?
        guard let signature = SecKeyCreateSignature(
            privateKey,
            .ecdsaSignatureMessageX962SHA256,
            dataBytes as CFData,
            &error
        ) as Data? else {
            let errMsg = error?.takeRetainedValue().localizedDescription ?? "Unknown error"
            result(FlutterError(code: "SIGN", message: "Signing failed: \(errMsg)", details: nil))
            return
        }

        result(signature.base64EncodedString())
    }

    private func extractVideoLocation(path: String, result: @escaping FlutterResult) {
        let url = URL(fileURLWithPath: path)
        let asset = AVURLAsset(url: url)

        let metadataItems = asset.metadata
        var latitude: Double? = nil
        var longitude: Double? = nil
        var creationDate: String? = nil

        // Check common metadata keys for location
        for item in metadataItems {
            if let key = item.commonKey {
                if key == .commonKeyLocation, let value = item.stringValue {
                    // Format is typically "+37.7749-122.4194/" (ISO 6709)
                    let parsed = parseISO6709(value)
                    latitude = parsed.0
                    longitude = parsed.1
                }
                if key == .commonKeyCreationDate, let value = item.stringValue {
                    creationDate = value
                }
            }
        }

        // Also check for GPS metadata in specific format keys
        if latitude == nil {
            for item in AVMetadataItem.metadataItems(from: metadataItems, filteredByIdentifier: .quickTimeMetadataLocationISO6709) {
                if let value = item.stringValue {
                    let parsed = parseISO6709(value)
                    latitude = parsed.0
                    longitude = parsed.1
                }
            }
        }

        if latitude != nil && longitude != nil {
            result([
                "latitude": latitude!,
                "longitude": longitude!,
                "creation_date": creationDate ?? ""
            ])
        } else {
            result(nil)
        }
    }

    /// Parse ISO 6709 location string like "+37.7749-122.4194/" or "+37.7749-122.4194+035.000/"
    private func parseISO6709(_ location: String) -> (Double?, Double?) {
        var str = location.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        // Remove altitude if present (third +/- component)
        // Format: +DD.DDDD-DDD.DDDD or +DD.DDDD-DDD.DDDD+AAA.AAA
        guard !str.isEmpty else { return (nil, nil) }

        var lat: Double? = nil
        var lon: Double? = nil

        // Find the second +/- sign (start of longitude)
        let chars = Array(str)
        var splitIndex = -1
        for i in 1..<chars.count {
            if chars[i] == "+" || chars[i] == "-" {
                if splitIndex == -1 {
                    splitIndex = i
                } else {
                    // Third component (altitude) - truncate
                    str = String(chars[0..<i])
                    break
                }
            }
        }

        if splitIndex > 0 {
            let latStr = String(str.prefix(splitIndex))
            let lonStr = String(str.suffix(from: str.index(str.startIndex, offsetBy: splitIndex)))
            lat = Double(latStr)
            lon = Double(lonStr)
        }

        return (lat, lon)
    }
}

// Helper for SHA-256 on older iOS versions
private func SHA256Hash(data: Data) -> Data {
    var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
    data.withUnsafeBytes {
        _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
    }
    return Data(hash)
}
