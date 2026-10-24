package org.campusroute.android;

import android.app.AppOpsManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.location.Criteria;
import android.location.Location;
import android.location.LocationManager;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.Process;
import android.os.SystemClock;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.FileDescriptor;
import java.io.PrintWriter;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;
import org.json.JSONObject;

public final class MockLocationService extends Service {
    public static volatile String status = "尚未启动。请先在电脑选择菜单1。";
    private static final String CHANNEL = "campusroute-location";
    private static final String STOP = "org.campusroute.android.STOP";
    private static final int PORT = 47653;
    private final Object locationLock = new Object();
    private final Set<String> providers = new HashSet<>();
    private volatile boolean running;
    private volatile String session;
    private volatile ServerSocket server;
    private volatile Socket client;
    private volatile Thread receiverThread;
    private volatile long receivedId;
    private volatile long repliedId;
    private volatile long lastApplyMs;
    private volatile String failedPhase = "none";
    private volatile long connectionId;
    private volatile long activeRequestId;
    private volatile long failedConnectionId;
    private volatile long failedRequestId;
    private volatile long failedAtMs;
    private volatile int readProgressBytes;
    private volatile long readStartedAtMs = -1;
    private volatile String disconnectReason = "none";
    private volatile CommandTrace lastTrace;
    private volatile Phase phase = new Phase("not_started");
    private LocationManager locations;
    private PowerManager.WakeLock wakeLock;

    private static final class Phase {
        final String name;
        final long sinceMs = SystemClock.elapsedRealtime();
        Phase(String name) { this.name = name; }
    }

    private void phase(String name) { phase = new Phase(name); }

    private void markFailure() {
        failedPhase = phase.name;
        failedConnectionId = connectionId;
        failedRequestId = activeRequestId;
        failedAtMs = SystemClock.elapsedRealtime();
    }

    private static final class Frame {
        final String text;
        final long started, firstByte, finished;
        final int bytes;
        Frame(String text, long started, long firstByte, long finished, int bytes) {
            this.text = text;
            this.started = started;
            this.firstByte = firstByte;
            this.finished = finished;
            this.bytes = bytes;
        }
    }

    private static final class CommandTrace {
        final long id, connection, readStarted, firstByte, readFinished, decoded;
        final int requestBytes;
        volatile String command = "decoding";
        volatile long handled = -1, writeStarted = -1, written = -1;
        volatile int replyBytes;
        CommandTrace(long id, long connection, Frame frame) {
            this.id = id;
            this.connection = connection;
            readStarted = frame.started;
            firstByte = frame.firstByte;
            readFinished = frame.finished;
            decoded = SystemClock.elapsedRealtime();
            requestBytes = frame.bytes;
        }
    }

    private static long duration(long end, long start) {
        return end < 0 || start < 0 ? -1 : end - start;
    }

    @Override public void onCreate() {
        super.onCreate();
        locations = (LocationManager) getSystemService(LOCATION_SERVICE);
        PowerManager power = (PowerManager) getSystemService(POWER_SERVICE);
        wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "CampusRoute:location");
        wakeLock.setReferenceCounted(false);
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL, "路线调试", NotificationManager.IMPORTANCE_LOW));
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        String nextSession = intent.getStringExtra("session");
        if (nextSession == null || !nextSession.matches("[0-9a-f]{48}")) {
            status = "无效会话，请从电脑重新连接。";
            stopSelf();
            return START_NOT_STICKY;
        }
        try {
            if (!locations.isLocationEnabled()) throw new SecurityException("请先打开系统定位。");
            AppOpsManager operations = (AppOpsManager) getSystemService(APP_OPS_SERVICE);
            if (operations.checkOpNoThrow(AppOpsManager.OPSTR_MOCK_LOCATION, Process.myUid(), getPackageName())
                    != AppOpsManager.MODE_ALLOWED) {
                throw new SecurityException("请在开发者选项中将 CampusRoute 选为模拟位置应用。");
            }
            PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
            PendingIntent stop = PendingIntent.getService(this, 1, new Intent(this, MockLocationService.class).setAction(STOP), PendingIntent.FLAG_IMMUTABLE);
            Notification notification = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentTitle("CampusRoute 路线调试")
                .setContentText("正在接收 USB 控制；点击停止可恢复定位")
                .setContentIntent(open).setOngoing(true)
                .addAction(android.R.drawable.ic_media_pause, "停止并恢复", stop).build();
            startForeground(1, notification);
            session = nextSession;
            if (running) {
                closeClient();
                clearLocations();
                status = "接收端已更新会话，等待电脑连接。";
            } else {
                running = true;
                receiverThread = new Thread(this::serve, "campusroute-receiver");
                receiverThread.start();
            }
        } catch (RuntimeException error) {
            status = "无法启动：" + error.getMessage();
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    private void serve() {
        try (ServerSocket listener = new ServerSocket(PORT, 1, InetAddress.getByName("127.0.0.1"))) {
            server = listener;
            listener.setSoTimeout(1000);
            status = "接收端已启动，等待电脑连接。";
            while (running) {
                String endReason = "";
                try (Socket socket = listener.accept()) {
                    if (!running) break;
                    client = socket;
                    connectionId++;
                    activeRequestId = 0;
                    disconnectReason = "connected";
                    socket.setSoTimeout(5000);
                    socket.setTcpNoDelay(true);
                    handle(socket);
                } catch (SocketTimeoutException error) {
                    // Accept timeout is harmless; a read timeout ends the location lease below.
                    if (client != null) {
                        markFailure();
                        disconnectReason = "read_timeout";
                        endReason = "接收指令超时";
                    }
                } catch (Exception error) {
                    markFailure();
                    disconnectReason = error.getClass().getSimpleName();
                    endReason = "连接异常：" + error.getClass().getSimpleName();
                } finally {
                    boolean hadClient = client != null;
                    client = null;
                    if (hadClient) {
                        try {
                            clearLocations();
                            status = (endReason.isEmpty() ? "电脑连接已结束" : endReason)
                                + "，模拟位置已移除；等待重新连接。";
                        } catch (RuntimeException error) {
                            status = "移除模拟位置失败：" + error.getMessage() + "；请重新授权或重启手机。";
                        }
                    }
                    phase("waiting_connection");
                }
            }
        } catch (IOException error) {
            if (running) status = "接收端错误：" + error.getMessage();
        } finally {
            server = null;
            if (running) stopSelf();
        }
    }

    private void handle(Socket socket) throws Exception {
        InputStream input = socket.getInputStream();
        OutputStream output = socket.getOutputStream();
        boolean authenticated = false;
        long previousId = 0;
        while (running) {
            phase("reading_command");
            Frame frame = readLine(input, socket);
            if (frame == null) {
                disconnectReason = "peer_eof";
                return;
            }
            JSONObject request = new JSONObject(frame.text);
            long id = request.getLong("id");
            receivedId = id;
            activeRequestId = id;
            CommandTrace trace = new CommandTrace(id, connectionId, frame);
            lastTrace = trace;
            JSONObject response = new JSONObject().put("id", id);
            boolean finish = false;
            try {
                if (id <= previousId) throw new IllegalArgumentException("指令序号必须递增。");
                previousId = id;
                String command = request.getString("command");
                trace.command = command.equals("hello") || command.equals("set") || command.equals("clear") ? command : "unknown";
                phase("handling_" + trace.command);
                if (!authenticated) {
                    byte[] expected = session.getBytes(StandardCharsets.UTF_8);
                    byte[] supplied = request.optString("token").getBytes(StandardCharsets.UTF_8);
                    if (!command.equals("hello") || request.optInt("protocol") != 1) {
                        throw new IllegalArgumentException("协议不匹配，请更新配套APK。");
                    }
                    if (!MessageDigest.isEqual(expected, supplied)) {
                        response.put("code", "session_not_ready");
                        throw new SecurityException("请在手机点击启动接收，更新本次会话。");
                    }
                    authenticated = true;
                    response.put("protocol", 1);
                    response.put("diagnostics", 2).put("app_version", "1.1.2");
                    status = "电脑已连接，等待位置。";
                } else if (command.equals("set")) {
                    double latitude = request.getDouble("latitude");
                    double longitude = request.getDouble("longitude");
                    double speed = request.optDouble("speed", 0);
                    double bearing = request.optDouble("bearing", 0);
                    if (!Double.isFinite(latitude) || !Double.isFinite(longitude) || Math.abs(latitude) > 90
                        || Math.abs(longitude) > 180 || !Double.isFinite(speed) || speed < 0 || speed > 100
                        || !Double.isFinite(bearing) || bearing < 0 || bearing >= 360) {
                        throw new IllegalArgumentException("无效位置参数。");
                    }
                    long startedMs = SystemClock.elapsedRealtime();
                    applyLocation(latitude, longitude, (float) speed, (float) bearing);
                    lastApplyMs = SystemClock.elapsedRealtime() - startedMs;
                    response.put("latitude", latitude).put("longitude", longitude).put("apply_ms", lastApplyMs);
                    status = "已应用 WGS84 坐标：" + latitude + ", " + longitude;
                } else if (command.equals("clear")) {
                    clearLocations();
                    response.put("cleared", true);
                    finish = true;
                    disconnectReason = "clear";
                } else {
                    throw new IllegalArgumentException("未知指令。");
                }
                response.put("ok", true);
            } catch (Exception error) {
                markFailure();
                disconnectReason = "command_error";
                response.put("ok", false).put("error", error.getMessage() == null ? error.toString() : error.getMessage());
                finish = true;
            }
            trace.handled = SystemClock.elapsedRealtime();
            byte[] reply = (response.toString() + "\n").getBytes(StandardCharsets.UTF_8);
            trace.replyBytes = reply.length;
            phase("writing_reply");
            trace.writeStarted = SystemClock.elapsedRealtime();
            output.write(reply);
            output.flush();
            trace.written = SystemClock.elapsedRealtime();
            repliedId = id;
            if (finish) return;
        }
    }

    private Frame readLine(InputStream input, Socket socket) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        long started = SystemClock.elapsedRealtime();
        readStartedAtMs = started;
        readProgressBytes = 0;
        long firstByte = -1;
        long deadline = started + 5000;
        while (bytes.size() < 4096) {
            long remaining = deadline - SystemClock.elapsedRealtime();
            if (remaining <= 0) throw new SocketTimeoutException("位置更新超时。");
            socket.setSoTimeout((int) remaining);
            int value = input.read();
            if (value == -1) return null;
            if (firstByte < 0) firstByte = SystemClock.elapsedRealtime();
            readProgressBytes++;
            if (value == '\n') return new Frame(new String(bytes.toByteArray(), StandardCharsets.UTF_8),
                started, firstByte, SystemClock.elapsedRealtime(), bytes.size() + 1);
            bytes.write(value);
        }
        throw new IOException("指令过长。");
    }

    @SuppressWarnings("deprecation")
    private void applyLocation(double latitude, double longitude, float speed, float bearing) {
        synchronized (locationLock) {
            if (!running) throw new IllegalStateException("接收端已停止。");
            for (String provider : new String[] {LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
                if (!providers.contains(provider)) {
                    phase("adding_" + provider);
                    locations.addTestProvider(provider, false, false, false, false, true, true, true,
                        Criteria.POWER_LOW, Criteria.ACCURACY_FINE);
                    providers.add(provider);
                    phase("enabling_" + provider);
                    locations.setTestProviderEnabled(provider, true);
                }
                Location location = new Location(provider);
                location.setLatitude(latitude);
                location.setLongitude(longitude);
                location.setAltitude(0);
                location.setAccuracy(3);
                location.setSpeed(speed);
                location.setBearing(bearing);
                location.setTime(System.currentTimeMillis());
                location.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos());
                phase("applying_" + provider);
                locations.setTestProviderLocation(provider, location);
            }
            phase("renewing_wake_lock");
            wakeLock.acquire(10000);
        }
    }

    private void clearLocations() {
        phase("waiting_cleanup_lock");
        synchronized (locationLock) {
            RuntimeException failure = null;
            for (String provider : new HashSet<>(providers)) {
                try {
                    phase("removing_" + provider);
                    locations.removeTestProvider(provider);
                    providers.remove(provider);
                } catch (RuntimeException error) { failure = error; }
            }
            if (wakeLock.isHeld()) wakeLock.release();
            if (failure != null) throw failure;
        }
    }

    @Override protected void dump(FileDescriptor fd, PrintWriter writer, String[] args) {
        // Read volatile snapshots only: a blocked location call must not block diagnostics
        // on locationLock. Never include a session token, command payload, or coordinates.
        Phase current = phase;
        long now = SystemClock.elapsedRealtime();
        writer.println("CR diagnostics=2 app_version=1.1.2 running=" + running);
        writer.println("CR connection=" + connectionId + " received_id=" + receivedId + " replied_id=" + repliedId);
        writer.println("CR phase=" + current.name + " phase_ms=" + (SystemClock.elapsedRealtime() - current.sinceMs));
        writer.println("CR last_apply_ms=" + lastApplyMs + " last_disconnect=" + disconnectReason);
        writer.println("CR last_failed_phase=" + failedPhase + " failed_connection=" + failedConnectionId
            + " failed_id=" + failedRequestId + " failed_age_ms=" + (failedAtMs == 0 ? -1 : now - failedAtMs));
        writer.println("CR current_read_bytes=" + readProgressBytes + " read_started_age_ms=" + duration(now, readStartedAtMs));
        CommandTrace trace = lastTrace;
        if (trace != null) {
            writer.println("CR trace_connection=" + trace.connection + " trace_id=" + trace.id + " command=" + trace.command);
            writer.println("CR request_bytes=" + trace.requestBytes + " read_wait_ms=" + duration(trace.firstByte, trace.readStarted)
                + " frame_read_ms=" + duration(trace.readFinished, trace.firstByte));
            writer.println("CR decode_ms=" + duration(trace.decoded, trace.readFinished)
                + " handle_ms=" + duration(trace.handled, trace.decoded)
                + " encode_ms=" + duration(trace.writeStarted, trace.handled));
            writer.println("CR reply_bytes=" + trace.replyBytes + " write_ms=" + duration(trace.written, trace.writeStarted)
                + " reply_age_ms=" + duration(now, trace.written));
        }
        Thread receiver = receiverThread;
        if (receiver != null) {
            writer.println("CR receiver_state=" + receiver.getState());
            StackTraceElement[] frames = receiver.getStackTrace();
            for (int i = 0; i < Math.min(14, frames.length); i++) writer.println("CR at " + frames[i]);
        }
    }

    private void closeClient() {
        Socket socket = client;
        if (socket != null) try { socket.close(); } catch (IOException ignored) { }
    }

    @Override public void onDestroy() {
        running = false;
        closeClient();
        ServerSocket listener = server;
        if (listener != null) try { listener.close(); } catch (IOException ignored) { }
        try {
            clearLocations();
            if (!status.startsWith("无法启动") && !status.startsWith("接收端错误")) {
                status = "接收端已停止，模拟位置已移除。";
            }
        } catch (RuntimeException error) {
            status = "停止时未能移除模拟位置：" + error.getMessage() + "；请重新授权或重启手机。";
        }
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
