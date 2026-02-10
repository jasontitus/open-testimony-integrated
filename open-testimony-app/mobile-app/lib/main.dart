import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'firebase_options.dart';
import 'screens/home_screen.dart';
import 'services/hardware_crypto_service.dart';
import 'services/upload_service.dart';
import 'services/video_service.dart';
import 'services/media_import_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Firebase (Crashlytics only, no Analytics)
  // Wrapped in try-catch so the app still works on devices without
  // Google Play Services (e.g. Kindle Fire, AOSP devices).
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );

    FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;

    PlatformDispatcher.instance.onError = (error, stack) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      return true;
    };
  } catch (e) {
    debugPrint('Firebase unavailable (no Google Play Services?): $e');
  }

  runApp(const OpenTestimonyApp());
}

class OpenTestimonyApp extends StatelessWidget {
  const OpenTestimonyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<HardwareCryptoService>(create: (_) => HardwareCryptoService()),
        Provider<UploadService>(create: (_) => UploadService()),
        Provider<VideoService>(create: (_) => VideoService()),
        Provider<MediaImportService>(create: (_) => MediaImportService()),
      ],
      child: MaterialApp(
        title: 'Open Testimony',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
          useMaterial3: true,
        ),
        home: const SafeArea(
          child: HomeScreen(),
        ),
      ),
    );
  }
}
