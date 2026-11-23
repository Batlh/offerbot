package io.github.batlh.offerbot

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.pm.PackageInstaller
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Toast
import java.lang.ref.WeakReference
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.io.File
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.HttpsURLConnection

class MainActivity : FlutterActivity() {
    private val prefs by lazy { getSharedPreferences("release_update", MODE_PRIVATE) }
    private val main = Handler(Looper.getMainLooper())
    private var foreground = false
    private val periodic = object : Runnable {
        override fun run() {
            check(false)
            main.postDelayed(this, interval)
        }
    }

    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        MethodChannel(engine.dartExecutor.binaryMessenger, "offerbot/updates").setMethodCallHandler { call, result ->
            if (call.method == "check") {
                check(true)
                result.success(null)
            } else result.notImplemented()
        }
    }

    override fun onResume() {
        super.onResume()
        foreground = true
        active = WeakReference(this)
        main.post(periodic)
    }

    override fun onPause() {
        foreground = false
        if (active.get() === this) active.clear()
        main.removeCallbacks(periodic)
        super.onPause()
    }

    private fun notice(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()

    private fun check(manual: Boolean) {
        if (installing.get()) return
        val now = System.currentTimeMillis()
        val pending = File(cacheDir, "updates/AngebotsBot.apk")
        val waiting = prefs.getBoolean("permission", false) || prefs.getBoolean("confirmLater", false)
        val elapsed = now - prefs.getLong("checked", 0)
        if (!manual && !waiting && elapsed in 0 until interval) return
        if (!busy.compareAndSet(false, true)) {
            if (manual) notice("Updateprüfung läuft.")
            return
        }
        if (manual) notice("Suche nach einem App-Update …")
        Thread {
            try {
                val installed = packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES)
                val current = installed.versionName.orEmpty()
                var version = prefs.getString("version", "").orEmpty()
                var hash = prefs.getString("digest", "").orEmpty()
                if (!waiting || !pending.isFile || !newer(version, current)) {
                    prefs.edit().putBoolean("permission", false).apply()
                    val release = JSONObject(connection("https://api.github.com/repos/Batlh/offerbot/releases/latest").useBody {
                        it.bufferedReader().readText()
                    })
                    val tag = release.getString("tag_name")
                    version = tag.removePrefix("v")
                    if (release.getBoolean("draft") || release.getBoolean("prerelease") ||
                        tag != "v" + version || !newer(version, current)) {
                        prefs.edit().putLong("checked", now).apply()
                        pending.delete()
                        if (manual) main.post { notice("Die App ist aktuell.") }
                        return@Thread
                    }
                    val assets = release.getJSONArray("assets")
                    val asset = (0 until assets.length()).map { assets.getJSONObject(it) }.firstOrNull {
                        it.optString("name") == "AngebotsBot.apk" && it.optString("state") == "uploaded"
                    } ?: error("APK ist noch nicht veröffentlicht.")
                    hash = asset.getString("digest")
                    require(hash.matches(Regex("sha256:[a-f0-9]{64}"))) { "SHA-256-Prüfsumme fehlt." }
                    val url = "https://github.com/Batlh/offerbot/releases/download/$tag/AngebotsBot.apk"
                    require(asset.getString("browser_download_url") == url) { "Unerwartete Downloadadresse." }
                    if (prefs.getString("digest", "") != hash || !pending.isFile || digest(pending) != hash) {
                        pending.parentFile!!.mkdirs()
                        val temp = File(pending.parentFile, "download.part")
                        try {
                            connection(url).useBody { input -> temp.outputStream().use { output -> input.copyTo(output) } }
                            require(temp.length() == asset.getLong("size") && digest(temp) == hash) { "Update-Datei beschädigt." }
                            check(temp.renameTo(pending)) { "APK konnte nicht gespeichert werden." }
                        } finally { temp.delete() }
                    }
                    prefs.edit().putString("version", version).putString("digest", hash).apply()
                }
                require(digest(pending) == hash) { "APK-Prüfsumme stimmt nicht." }
                val archive = packageManager.getPackageArchiveInfo(pending.path, PackageManager.GET_SIGNATURES)
                    ?: error("Ungültige APK.")
                require(archive.packageName == packageName && archive.versionName == version &&
                    archive.versionCode > installed.versionCode &&
                    !archive.signatures.isNullOrEmpty() && archive.signatures!!.toSet() == installed.signatures!!.toSet()
                ) { "Paket, Version oder Signatur stimmen nicht." }
                main.post {
                    if (!foreground || isFinishing || isDestroyed) return@post
                    prefs.edit().putLong("checked", now).putBoolean("permission", false).putBoolean("confirmLater", false).apply()
                    try {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !packageManager.canRequestPackageInstalls()) {
                            if (waiting) {
                                notice("Zum Installieren bitte AngebotsBot als App-Quelle zulassen. Erneut über das Update-Menü möglich.")
                            } else {
                                android.app.AlertDialog.Builder(this)
                                    .setTitle("Update auf $version")
                                    .setMessage("Die APK ist geprüft. Android benötigt einmalig die Erlaubnis, dass AngebotsBot Updates installieren darf.")
                                    .setNegativeButton("Später", null)
                                    .setPositiveButton("Einstellungen") { _, _ ->
                                        prefs.edit().putBoolean("permission", true).apply()
                                        startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
                                    }.show()
                            }
                        } else {
                            installUpdate(pending)
                        }
                    } catch (e: Exception) { notice("Installation: ${e.localizedMessage}") }
                }
            } catch (e: Exception) {
                if (manual || waiting) main.post { notice("Update: ${e.localizedMessage}") }
                prefs.edit().putBoolean("permission", false).putLong("checked", now - interval + 15 * 60_000).apply()
            } finally { busy.set(false) }
        }.start()
    }

    private fun installUpdate(apk: File) {
        if (!installing.compareAndSet(false, true)) return
        Thread {
            try {
                val installer = packageManager.packageInstaller
                val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
                params.setAppPackageName(packageName)
                params.setSize(apk.length())
                if (Build.VERSION.SDK_INT >= 31) {
                    params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
                }
                val id = installer.createSession(params)
                try {
                    installer.openSession(id).use { session ->
                        apk.inputStream().use { input ->
                            session.openWrite("base.apk", 0, apk.length()).use { output ->
                                input.copyTo(output)
                                session.fsync(output)
                            }
                        }
                        val intent = Intent(this, UpdateResult::class.java)
                        val mutable = if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
                        val result = PendingIntent.getBroadcast(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or mutable)
                        session.commit(result.intentSender)
                    }
                } catch (error: Exception) {
                    installer.abandonSession(id)
                    throw error
                }
            } catch (error: Exception) {
                main.post { notice("Installation fehlgeschlagen: ${error.localizedMessage}") }
            } finally { installing.set(false) }
        }.start()
    }

    companion object {
        internal var active = WeakReference<MainActivity>(null)
        private const val interval = 6 * 60 * 60_000L
        private val busy = AtomicBoolean(false)
        private val installing = AtomicBoolean(false)

        private fun newer(value: String, current: String): Boolean {
            val format = Regex("[0-9]+\\.[0-9]+\\.[0-9]+")
            if (!value.matches(format) || !current.matches(format)) return false
            val a = value.split(".").map { it.toInt() }
            val b = current.split(".").map { it.toInt() }
            for (i in a.indices) if (a[i] != b[i]) return a[i] > b[i]
            return false
        }

        private fun digest(file: File): String {
            val md = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { stream ->
                val bytes = ByteArray(65536)
                while (true) {
                    val count = stream.read(bytes)
                    if (count < 0) break
                    md.update(bytes, 0, count)
                }
            }
            return "sha256:" + md.digest().joinToString("") { "%02x".format(it) }
        }

        private fun connection(address: String): HttpsURLConnection {
            var url = URL(address)
            repeat(6) {
                require(url.protocol == "https" && url.host in setOf("api.github.com", "github.com",
                    "release-assets.githubusercontent.com", "objects.githubusercontent.com")) { "Unbekannter Downloadanbieter." }
                val c = url.openConnection() as HttpsURLConnection
                c.instanceFollowRedirects = false
                c.connectTimeout = 15000
                c.readTimeout = 45000
                c.setRequestProperty("User-Agent", "AngebotsBot-Updater")
                try {
                    val status = c.responseCode
                    if (status == 200) return c
                    if (status !in setOf(301, 302, 303, 307, 308)) error("GitHub antwortet mit HTTP $status.")
                    url = URL(url, c.getHeaderField("Location"))
                } catch (e: Exception) { c.disconnect(); throw e }
                c.disconnect()
            }
            error("Zu viele Weiterleitungen.")
        }

        private fun <T> HttpsURLConnection.useBody(read: (java.io.InputStream) -> T): T =
            try { inputStream.use(read) } finally { disconnect() }
    }
}


class UpdateResult : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val prefs = context.getSharedPreferences("release_update", Context.MODE_PRIVATE)
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            val next = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
            val activity = MainActivity.active.get()
            if (activity != null && next != null) {
                try {
                    activity.startActivity(next)
                    return
                } catch (_: android.content.ActivityNotFoundException) { /* Beim nächsten Öffnen erneut versuchen. */ }
            }
            val session = intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1)
            if (session >= 0) runCatching { context.packageManager.packageInstaller.abandonSession(session) }
            prefs.edit().putBoolean("confirmLater", true).apply()
        } else if (status == PackageInstaller.STATUS_SUCCESS) {
            prefs.edit().remove("permission").remove("confirmLater").apply()
            File(context.cacheDir, "updates/AngebotsBot.apk").delete()
        } else if (MainActivity.active.get() != null) {
            Toast.makeText(context, "Update wurde nicht installiert. Ein neuer Versuch ist im App-Menü möglich.",
                Toast.LENGTH_LONG).show()
        }
    }
}
