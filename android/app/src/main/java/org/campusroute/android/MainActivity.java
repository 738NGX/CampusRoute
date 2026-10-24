package org.campusroute.android;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView status;
    private String session = "";
    private final Runnable refresh = new Runnable() {
        @Override public void run() {
            status.setText(MockLocationService.status);
            handler.postDelayed(this, 1000);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        session = getIntent().getStringExtra("session");
        ScrollView scroll = new ScrollView(this);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (24 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);
        // Android 15+ enforces edge-to-edge for targetSdk 35; keep controls below system bars.
        layout.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(padding + insets.getSystemWindowInsetLeft(), padding + insets.getSystemWindowInsetTop(),
                padding + insets.getSystemWindowInsetRight(), padding + insets.getSystemWindowInsetBottom());
            return insets;
        });
        scroll.addView(layout);
        TextView title = new TextView(this);
        title.setText("CampusRoute 1.1.2 · Android 接收端");
        title.setTextSize(24);
        layout.addView(title);
        TextView instructions = new TextView(this);
        instructions.setText("1. 在开发者选项中，将 CampusRoute 选为模拟位置信息应用。\n\n"
            + "2. 打开系统定位，并允许本应用使用位置。\n\n"
            + "3. 电脑选择菜单1后，回到这里点击“启动接收”。\n\n"
            + "USB 断开或5秒未收到位置更新时，会尝试移除模拟位置。暂停和中止期间由电脑持续保持位置。\n"
            + "这些位置带有 Android 模拟标记，用于位置功能调试。\n");
        instructions.setTextSize(16);
        layout.addView(instructions);
        button(layout, "打开开发者选项", () -> {
            try { startActivity(new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS)); }
            catch (RuntimeException error) { MockLocationService.status = "请手动打开系统开发者选项。"; }
        });
        button(layout, "允许定位权限", this::requestPermissionsForService);
        button(layout, "启动接收", this::startReceiver);
        button(layout, "停止并恢复", () -> {
            stopService(new Intent(this, MockLocationService.class));
        });
        status = new TextView(this);
        status.setTextSize(16);
        layout.addView(status);
        setContentView(scroll);
    }

    private void button(LinearLayout layout, String label, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(view -> action.run());
        layout.addView(button);
    }

    private void requestPermissionsForService() {
        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(new String[] {Manifest.permission.ACCESS_COARSE_LOCATION,
                Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.POST_NOTIFICATIONS}, 1);
        } else {
            requestPermissions(new String[] {Manifest.permission.ACCESS_COARSE_LOCATION,
                Manifest.permission.ACCESS_FINE_LOCATION}, 1);
        }
    }

    private void startReceiver() {
        if (session == null || !session.matches("[0-9a-f]{48}")) {
            MockLocationService.status = "请先在电脑选择菜单1，建立本次 USB 会话。";
            return;
        }
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED
            && checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissionsForService();
            MockLocationService.status = "授权完成后，请再次点击启动接收。";
            return;
        }
        try {
            Intent intent = new Intent(this, MockLocationService.class);
            intent.putExtra("session", session);
            startForegroundService(intent);
        } catch (RuntimeException error) {
            MockLocationService.status = "启动失败：" + error.getMessage();
        }
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        session = intent.getStringExtra("session");
        MockLocationService.status = "收到电脑连接请求，请点击启动接收。";
    }

    @Override protected void onResume() {
        super.onResume();
        handler.post(refresh);
    }

    @Override protected void onPause() {
        handler.removeCallbacks(refresh);
        super.onPause();
    }
}
