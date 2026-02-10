import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      throw UnsupportedError('Web platform is not configured for Firebase.');
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.iOS:
        return ios;
      case TargetPlatform.macOS:
        throw UnsupportedError('macOS is not configured for Firebase.');
      case TargetPlatform.android:
        return android;
      case TargetPlatform.windows:
        throw UnsupportedError('Windows is not configured for Firebase.');
      case TargetPlatform.linux:
        throw UnsupportedError('Linux is not configured for Firebase.');
      default:
        throw UnsupportedError('${defaultTargetPlatform.name} is not supported.');
    }
  }

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyBmXwUpeMFKmBiMp8_Bz8M60dq54ZtpcAc',
    appId: '1:416996271373:android:cbb0441417c1a59eacbc44',
    messagingSenderId: '416996271373',
    projectId: 'open-testimony',
    storageBucket: 'open-testimony.firebasestorage.app',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyCnO9P8OW0Roo0TCxevcw9gsf-UVgltR_4',
    appId: '1:416996271373:ios:beb617566fb8ec19acbc44',
    messagingSenderId: '416996271373',
    projectId: 'open-testimony',
    storageBucket: 'open-testimony.firebasestorage.app',
    iosBundleId: 'com.opentestimony.app',
  );
}
