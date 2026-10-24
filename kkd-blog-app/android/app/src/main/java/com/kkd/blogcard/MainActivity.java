package com.kkd.blogcard;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.io.InputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 웹 UI(assets/www)를 띄우고, 웹에서 할 수 없는 일(카드 PNG 캡처·갤러리 저장·클립보드·공유·설정 저장)을
 * JavaScript 브리지 "Android" 로 제공한다.
 */
public class MainActivity extends Activity {

    // 앱 자산을 https 출처로 제공 → fetch/CORS/localStorage 가 일반 웹페이지처럼 동작
    static final String ASSET_HOST = "appassets.androidplatform.net";
    static final String APP_URL = "https://" + ASSET_HOST + "/assets/www/index.html";
    static final int REQ_PICK = 1001;
    static final int CARD_CSS_WIDTH = 900;
    static final int OUT_WIDTH = 1800; // 저장 이미지 가로 픽셀 (카드 900px × 2배)

    WebView web;
    WebView renderer;
    FrameLayout root;
    ValueCallback<Uri[]> fileCallback;
    SharedPreferences prefs;

    String pendingRenderId;
    String pendingRenderName;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 화면 밖 영역까지 전체 문서를 그리려면 WebView 생성 전에 호출해야 함
        WebView.enableSlowWholeDocumentDraw();
        prefs = getSharedPreferences("kkd", MODE_PRIVATE);

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        // 카드 캡처 전용 WebView: 메인 화면 뒤에 깔려 있어 사용자에게 보이지 않음
        renderer = new WebView(this);
        setupWebView(renderer);
        renderer.addJavascriptInterface(new RenderBridge(), "KKDRender");
        renderer.setWebViewClient(new AssetClient());
        int w = Math.round(CARD_CSS_WIDTH * getResources().getDisplayMetrics().density);
        root.addView(renderer, new FrameLayout.LayoutParams(w, w));

        web = new WebView(this);
        setupWebView(web);
        web.addJavascriptInterface(new AppBridge(), "Android");
        web.setWebViewClient(new AssetClient());
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("image/*");
                i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try {
                    startActivityForResult(Intent.createChooser(i, "이미지 선택"), REQ_PICK);
                } catch (Exception e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });
        web.setBackgroundColor(Color.WHITE);
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        setContentView(root);
        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else web.loadUrl(APP_URL);
    }

    void setupWebView(WebView v) {
        WebSettings s = v.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);
        s.setMediaPlaybackRequiresUserGesture(true);
        s.setTextZoom(100);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != REQ_PICK || fileCallback == null) {
            super.onActivityResult(requestCode, resultCode, data);
            return;
        }
        Uri[] result = null;
        if (resultCode == RESULT_OK && data != null) {
            ClipData clip = data.getClipData();
            if (clip != null) {
                result = new Uri[clip.getItemCount()];
                for (int i = 0; i < clip.getItemCount(); i++) result[i] = clip.getItemAt(i).getUri();
            } else if (data.getData() != null) {
                result = new Uri[]{data.getData()};
            }
        }
        fileCallback.onReceiveValue(result);
        fileCallback = null;
    }

    /** https://appassets.androidplatform.net/assets/... 요청을 APK assets 로 응답 */
    class AssetClient extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
            Uri u = req.getUrl();
            if (!ASSET_HOST.equals(u.getHost())) return null;
            String path = u.getPath();
            if (path == null || !path.startsWith("/assets/")) return notFound();
            try {
                InputStream in = getAssets().open(path.substring("/assets/".length()));
                return new WebResourceResponse(mimeOf(path), "utf-8", in);
            } catch (Exception e) {
                return notFound();
            }
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
            Uri u = req.getUrl();
            if (ASSET_HOST.equals(u.getHost())) return false;
            // 외부 링크는 브라우저로
            try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
            return true;
        }
    }

    static WebResourceResponse notFound() {
        WebResourceResponse r = new WebResourceResponse("text/plain", "utf-8", null);
        r.setStatusCodeAndReasonPhrase(404, "Not Found");
        return r;
    }

    static String mimeOf(String path) {
        if (path.endsWith(".html")) return "text/html";
        if (path.endsWith(".js")) return "application/javascript";
        if (path.endsWith(".css")) return "text/css";
        if (path.endsWith(".png")) return "image/png";
        if (path.endsWith(".svg")) return "image/svg+xml";
        if (path.endsWith(".json")) return "application/json";
        return "application/octet-stream";
    }

    void callJs(final String script) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() { web.evaluateJavascript(script, null); }
        });
    }

    static String jsString(String s) {
        if (s == null) return "null";
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '<': b.append("\\u003c"); break;
                default:
                    if (c < 0x20 || c == 0x2028 || c == 0x2029) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.append('"').toString();
    }

    void finishRender(boolean ok, String uriOrError, String name) {
        String id = pendingRenderId;
        pendingRenderId = null;
        if (id == null) return;
        callJs("window.__kkdRendered(" + jsString(id) + "," + ok + "," + jsString(uriOrError) + "," + jsString(name) + ")");
    }

    /** 캡처 WebView 를 카드 높이에 맞춘 뒤 2배 해상도 PNG 로 그려 갤러리에 저장 */
    void captureCard(final float cssHeight) {
        final float density = getResources().getDisplayMetrics().density;
        final int w = Math.round(CARD_CSS_WIDTH * density);
        final int h = Math.max(1, Math.round(cssHeight * density));
        renderer.setLayoutParams(new FrameLayout.LayoutParams(w, h));
        renderer.postDelayed(new Runnable() {
            @Override
            public void run() {
                try {
                    float scale = (float) OUT_WIDTH / renderer.getWidth();
                    int outH = Math.round(renderer.getHeight() * scale);
                    Bitmap bmp = Bitmap.createBitmap(OUT_WIDTH, outH, Bitmap.Config.ARGB_8888);
                    Canvas c = new Canvas(bmp);
                    c.drawColor(Color.WHITE);
                    c.scale(scale, scale);
                    renderer.draw(c);
                    String name = pendingRenderName + "_" + new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.KOREA).format(new Date()) + ".png";
                    Uri uri = savePng(bmp, name);
                    bmp.recycle();
                    finishRender(true, uri.toString(), name);
                } catch (Throwable t) {
                    finishRender(false, "카드 이미지 저장 실패: " + t.getMessage(), null);
                } finally {
                    renderer.loadUrl("about:blank");
                }
            }
        }, 700);
    }

    Uri savePng(Bitmap bmp, String name) throws Exception {
        ContentValues v = new ContentValues();
        v.put(MediaStore.Images.Media.DISPLAY_NAME, name);
        v.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
        v.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/KKDBlog");
        v.put(MediaStore.Images.Media.IS_PENDING, 1);
        ContentResolver cr = getContentResolver();
        Uri uri = cr.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
        if (uri == null) throw new Exception("MediaStore insert 실패");
        OutputStream os = cr.openOutputStream(uri);
        try {
            if (!bmp.compress(Bitmap.CompressFormat.PNG, 100, os)) throw new Exception("PNG 인코딩 실패");
        } finally {
            if (os != null) os.close();
        }
        v.clear();
        v.put(MediaStore.Images.Media.IS_PENDING, 0);
        cr.update(uri, v, null, null);
        return uri;
    }

    /** 캡처용 페이지가 글꼴 로딩을 마치면 카드 높이를 알려 옴 */
    class RenderBridge {
        @JavascriptInterface
        public void ready(final float cssHeight) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() { if (pendingRenderId != null) captureCard(cssHeight); }
            });
        }
    }

    class AppBridge {
        @JavascriptInterface
        public String getPref(String key) { return prefs.getString(key, ""); }

        @JavascriptInterface
        public void setPref(String key, String value) { prefs.edit().putString(key, value).apply(); }

        @JavascriptInterface
        public void renderCard(final String html, final String id, final String name) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (pendingRenderId != null) finishRender(false, "이전 저장 작업이 아직 진행 중입니다.", null);
                    pendingRenderId = id;
                    pendingRenderName = (name == null || name.isEmpty()) ? "card" : name;
                    int w = Math.round(CARD_CSS_WIDTH * getResources().getDisplayMetrics().density);
                    renderer.setLayoutParams(new FrameLayout.LayoutParams(w, w));
                    renderer.loadDataWithBaseURL("https://" + ASSET_HOST + "/assets/www/", html, "text/html", "utf-8", null);
                    // 글꼴 서버 응답이 없을 때도 멈추지 않도록 안전장치
                    renderer.postDelayed(new Runnable() {
                        @Override
                        public void run() {
                            if (id.equals(pendingRenderId)) finishRender(false, "카드 렌더링 시간이 초과됐습니다. 다시 시도해 주세요.", null);
                        }
                    }, 20000);
                }
            });
        }

        @JavascriptInterface
        public void copyText(String text) {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("블로그 원고", text));
        }

        @JavascriptInterface
        public void share(final String text, final String imageUri) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Intent send = new Intent(Intent.ACTION_SEND);
                    send.setType("image/png");
                    send.putExtra(Intent.EXTRA_STREAM, Uri.parse(imageUri));
                    send.putExtra(Intent.EXTRA_TEXT, text);
                    send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    Intent blog = new Intent(send).setPackage("com.nhn.android.blog");
                    try {
                        startActivity(blog);
                        Toast.makeText(MainActivity.this, "원고는 클립보드에 복사됐습니다. 에디터에 붙여 넣으세요.", Toast.LENGTH_LONG).show();
                    } catch (Exception e) {
                        startActivity(Intent.createChooser(send, "블로그 앱 선택"));
                    }
                }
            });
        }

        @JavascriptInterface
        public void toast(final String msg) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() { Toast.makeText(MainActivity.this, msg, Toast.LENGTH_SHORT).show(); }
            });
        }
    }

    @Override
    protected void onDestroy() {
        root.removeAllViews();
        web.destroy();
        renderer.destroy();
        super.onDestroy();
    }
}
