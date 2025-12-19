# auto-blog (FastAPI + HTMX)

LLM で WordPress の下書きを 10 本まとめて生成し、Application Password 経由で WP に下書き投稿するツール。ブラウザからテーマを入力するだけで、Plan → Draft → QC/Revise → FAQ → WP 下書き投稿までをジョブとして実行し、進捗・結果を HTMX で確認できる。

## 概要
- できること: テーマを入力すると、10 本分のアウトライン・本文・FAQ を生成し、WordPress に下書き投稿する。進捗/結果をブラウザで確認可能。
- 入力項目: WordPress URL / ユーザー名 / Application Password / テーマ / キーワード（任意） / 本数（デフォルト 10）。
- 出力: WP の下書き URL（成功時）、QC 状態、ログ。

## 事前準備
1. WordPress で Application Password を発行  
   - ユーザープロファイル > Application Passwords から新規発行。  
   - 権限は「投稿の作成」ができるユーザーで発行すること（管理者推奨、公開サイトでは専用ユーザーを推奨）。
2. HTTPS 推奨  
   - Basic 認証（Application Password）が含まれるため、HTTPS 経由で接続する。

## クイックスタート
```bash
# 1) 起動
docker compose up -d --build

# 2) ブラウザでアクセス
open http://localhost:8000
```
- 画面で WordPress URL, Username, Application Password, テーマ等を入力して「バッチ実行」。

## 設定
- `.env`（例）  
  - `OPENAI_API_KEY=...` など LLM アクセスキー（使うモデルに合わせて設定）。  
  - 設定よりフォーム入力が優先される。  
- 推奨値  
  - desired_count: 10（仕様に合わせる）  
  - タイムアウトが発生する場合は WP 側の応答時間を確認。  
- Markdown → HTML 変換はデフォルトで有効（WordPressClient が内部で変換）。必要なら設定で無効化可能。

## 実行フロー（進捗の見方）
1. `/run` をフォームから POST → job_id が発行され queued → running に遷移。  
2. HTMX が `/progress/{job_id}` をポーリングし、`current/total` と最新ログ、成功した WP URL を表示。  
3. すべて完了で `done`、エラー時は `failed`。  
4. `/result/{job_id}` で全記事の結果一覧（Draft OK/NG、WP OK/NG、URL/エラー）を確認。

## セキュリティ注意
- Application Password はログに出さない（コードでも保管しない、フォーム入力をログしない）。  
- HTTPS でアクセスする。  
- 公開運用は非推奨。少なくとも Basic 認証や IP 制限をかける。  
- 生成した下書きは公開前に必ず目視確認。

## トラブルシュート
- WP 401/403: Application Password/ユーザー権限を再確認。URL が HTTPS か確認。  
- タイムアウト: WordPress 側の応答遅延、ネットワーク、リトライ回数を確認。  
- JSON parse 失敗: LLM 出力が壊れた可能性。retry でも直らない場合はプロンプト/テンプレを確認。  
- LLM 生成が崩れる: outline id 埋め込みや必須フィールド欠落が QC で検出される。テンプレ修正か再実行。  
- WP 投稿失敗: `progress` の最新ログで HTTP ステータスとメッセージを確認。

## 開発者向け
- ローカル起動:  
  ```bash
  uvicorn app.server:app --reload
  ```  
  LLMOrchestrator のセットアップは `configure_orchestrator` を起動時に呼び出す実装を追加すること。
- テスト:  
  ```bash
  python -m py_compile $(find domain usecases app infrastructure -name '*.py')
  ```  
  （必要に応じて pytest 等を追加してください）
- ディレクトリ構成:  
  - `app/`: FastAPI/HTMX ルータ、プロンプト関連。  
  - `domain/`: モデル定義（Article/Batch/Job など）。  
  - `usecases/`: オーケストレーション、ジョブ実行。  
  - `infrastructure/`: WordPress クライアント、永続化ストア（InMemory など）。  
  - `templates/`: ページ/パーシャル（HTMX）。

## 既知の制約
- WP 投稿は Application Password の Basic 認証のみ対応。  
- Markdown → HTML は簡易変換（デフォルト）。高度な変換やブロックエディタ最適化は未対応。  
- カテゴリ URL/付与などは SiteAdapter 実装次第（デフォルト未対応）。  
- バッチは 10 本前提で設計（desired_count を変えると挙動未検証）。  
