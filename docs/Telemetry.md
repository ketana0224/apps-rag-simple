## 4. 推奨解決策（最終合意版）

### 4.1 【第一推奨】`azure-monitor-opentelemetry` を `post_fork` フックで初期化

**両エージェントが合意した最終推奨。**

#### 依存関係のインストール

```bash
pip install azure-monitor-opentelemetry
```

`requirements.txt` に追記：
```
azure-monitor-opentelemetry>=1.0.0
```

#### `gunicorn.conf.py` の実装

```python
# gunicorn.conf.py

import os

# gunicorn 設定
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = "info"


def post_fork(server, worker):
    """
    fork 後に各ワーカープロセスで Application Insights を初期化する。

    重要：親プロセス（pre_fork）での初期化は禁止。
    gunicorn は fork() でワーカーを生成するため、
    親プロセスで初期化した Exporter スレッドは fork 後に引き継がれず、
    テレメトリデータが送信されなくなる。
    """
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string:
        server.log.warning(
            "APPLICATIONINSIGHTS_CONNECTION_STRING が設定されていません。"
            "Application Insights の初期化をスキップします。"
        )
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(
            connection_string=connection_string,
        )
        server.log.info(
            f"Application Insights 初期化完了 (worker PID: {worker.pid})"
        )
    except Exception as e:
        server.log.error(f"Application Insights 初期化失敗: {e}")
```

#### App Service の起動コマンド設定例

```bash
# Azure Portal > 設定 > 全般設定 > スタートアップコマンド
gunicorn myapp:app -c gunicorn.conf.py
```

#### App Settings（環境変数）設定

| キー | 値 | 必須 |
|---|---|---|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `InstrumentationKey=xxx;...` | ✅ 必須 |
| `OTEL_SERVICE_NAME` | `my-app-service` | 強く推奨 |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment=production` | 推奨 |
