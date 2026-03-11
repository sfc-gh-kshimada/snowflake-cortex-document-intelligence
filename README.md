# Snowflake Cortex Document Intelligence

Snowflake Cortex AI 関数を使用したドキュメント抽出・分析 Streamlit アプリケーションです。

![Streamlit in Snowflake](https://img.shields.io/badge/Streamlit-in%20Snowflake-blue)
![Cortex AI](https://img.shields.io/badge/Cortex-AI%20Functions-green)

## 主な機能

| 関数 | 用途 | 対応形式 |
|------|------|----------|
| **AI_PARSE_DOCUMENT** | テキスト・構造・画像抽出 | PDF, DOCX, PPTX, PNG, JPG等 |
| **AI_EXTRACT** | 構造化データ抽出 | PDF, DOCX, XLSX, PNG等 |
| **AI_COMPLETE** | 質問応答・分析 | PDF, DOCX, XLSX (モデル依存) |
| **AI_SUMMARIZE** | テキスト要約 | テキスト |
| **AI_TRANSLATE** | 翻訳 | テキスト |

### 特徴

- 📄 **マルチフォーマット対応**: PDF, Word, Excel, PowerPoint, 画像
- 🖼️ **画像抽出・解説**: PDFから画像を抽出し、AIが文脈を踏まえて解説
- 🔍 **構造化抽出**: 請求書、名刺、表データなどを JSON 形式で抽出
- 💬 **インタラクティブQ&A**: ドキュメントに対する自由な質問
- 📊 **複数ファイル比較**: 2つのドキュメントを比較分析

## 対応モデル (AI_COMPLETE)

| モデル | 最大サイズ | 対応形式 | 特徴 |
|--------|-----------|----------|------|
| gemini-3-pro | 10MB | PDF, TXT, MD | 大容量・最大900ページ |
| claude-sonnet-4-5 | 4.5MB | PDF, DOCX, XLSX等 | バランス型 |
| claude-opus-4-5 | 4.5MB | PDF, DOCX, XLSX等 | 高精度 |
| claude-haiku-4-5 | 4.5MB | PDF, DOCX, XLSX等 | 高速・低コスト |
| claude-4-sonnet | 4.5MB | PDF, DOCX, XLSX等 | Claude 4 |
| claude-4-opus | 4.5MB | PDF, DOCX, XLSX等 | Claude 4 高精度 |
| claude-3-7-sonnet | 4.5MB | PDF, DOCX, XLSX等 | Claude 3.7 |

## 前提条件

- Snowflake アカウント
- `SNOWFLAKE.CORTEX_USER` データベースロール
- ウェアハウス

## デプロイ方法

### 方法1: Snowsight (GUI) でデプロイ

Snowflake CLI不要。Snowsight上で完結します。

#### Step 1: Snowflakeオブジェクト作成

Snowsight のワークシートで以下を実行:

```sql
-- データベース・スキーマ作成
CREATE DATABASE IF NOT EXISTS <YOUR_DATABASE>;
CREATE SCHEMA IF NOT EXISTS <YOUR_DATABASE>.<YOUR_SCHEMA>;

-- ファイル保存用ステージ作成
CREATE STAGE IF NOT EXISTS <YOUR_DATABASE>.<YOUR_SCHEMA>.papers
  DIRECTORY = (ENABLE = TRUE)
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');
```

#### Step 2: Streamlit アプリ作成

1. Snowsight 左メニュー → **Streamlit** → **+ Streamlit App**
2. 以下を設定:
   - **App name**: `DOCUMENT_EXTRACTION_POC`
   - **App location**: `<YOUR_DATABASE>.<YOUR_SCHEMA>`
   - **Warehouse**: `<YOUR_WAREHOUSE>`
3. **Create** をクリック

#### Step 3: コードを貼り付け

1. エディタが開いたら、デフォルトコードを全て削除
2. `streamlit_app.py` の内容を全てコピー＆ペースト
3. **14行目**のステージ名を変更:
   ```python
   STAGE_NAME = "<YOUR_DATABASE>.<YOUR_SCHEMA>.papers"
   ```
4. **Run** をクリック

#### Step 4: パッケージ設定

1. 左サイドバーの **Packages** をクリック
2. `streamlit` を検索し、バージョン `1.35.0` 以上を選択
3. **Run** で動作確認

---

### 方法2: Snowflake CLI でデプロイ

自動化やCI/CD向け。

#### Step 1: リポジトリをクローン

```bash
git clone https://github.com/sfc-gh-kshimada/snowflake-cortex-document-intelligence.git
cd snowflake-cortex-document-intelligence
```

#### Step 2: Snowflake オブジェクト作成

```sql
CREATE DATABASE IF NOT EXISTS <YOUR_DATABASE>;
CREATE SCHEMA IF NOT EXISTS <YOUR_DATABASE>.<YOUR_SCHEMA>;

CREATE STAGE IF NOT EXISTS <YOUR_DATABASE>.<YOUR_SCHEMA>.papers
  DIRECTORY = (ENABLE = TRUE)
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');
```

#### Step 3: 設定ファイル編集

**snowflake.yml**
```yaml
definition_version: 2
entities:
  document_extraction_poc:
    type: streamlit
    identifier:
      name: DOCUMENT_EXTRACTION_POC
      database: <YOUR_DATABASE>       # ← 変更
      schema: <YOUR_SCHEMA>           # ← 変更
    query_warehouse: <YOUR_WAREHOUSE> # ← 変更
    main_file: streamlit_app.py
    artifacts:
      - streamlit_app.py
      - environment.yml
```

**streamlit_app.py (14行目)**
```python
STAGE_NAME = "<YOUR_DATABASE>.<YOUR_SCHEMA>.papers"
```

#### Step 4: デプロイ

```bash
snow streamlit deploy --connection <YOUR_CONNECTION> --replace
```

---

### 方法3: SPCS (Container Runtime) でデプロイ

External Access Integration (EAI) が利用可能な環境では、Snowpark Container Services を使用してコンテナランタイムでデプロイできます。PyPI からのパッケージインストールが可能になり、より柔軟な依存関係管理ができます。

#### 前提条件

- External Access Integration が設定済み
- Compute Pool が作成済み

#### Step 1: Compute Pool 作成 (未作成の場合)

```sql
CREATE COMPUTE POOL IF NOT EXISTS <YOUR_COMPUTE_POOL>
  MIN_NODES = 1
  MAX_NODES = 5
  INSTANCE_FAMILY = CPU_X64_XS;
```

#### Step 2: snowflake.yml を編集

```yaml
definition_version: 2
entities:
  document_extraction_poc:
    type: streamlit
    identifier:
      name: DOCUMENT_EXTRACTION_POC
      database: <YOUR_DATABASE>
      schema: <YOUR_SCHEMA>
    query_warehouse: <YOUR_WAREHOUSE>
    compute_pool: <YOUR_COMPUTE_POOL>                    # ← 追加
    runtime_name: SYSTEM$ST_CONTAINER_RUNTIME_PY3_11     # ← 追加
    main_file: streamlit_app.py
    artifacts:
      - streamlit_app.py
      - pyproject.toml                                   # ← environment.yml の代わり
```

#### Step 3: pyproject.toml で依存関係を指定

```toml
[project]
name = "document_extraction_poc"
version = "1.0.0"
dependencies = [
    "streamlit>=1.35.0"
]
```

#### Step 4: デプロイ

```bash
snow streamlit deploy --connection <YOUR_CONNECTION> --replace
```

> **Note**: EAI が未設定の場合、PyPI へのアクセスエラーが発生します。その場合は方法1または方法2 (Warehouse ベース) をご利用ください。

## 使い方

1. Snowsight でアプリにアクセス
2. サイドバーからファイルをアップロード
3. タブで機能を選択:

| タブ | 機能 |
|------|------|
| 🔍 AI_PARSE_DOCUMENT | テキスト・画像抽出、画像のAI解説 |
| 📊 AI_EXTRACT | 構造化データ抽出 (請求書、名刺等) |
| 💬 AI_COMPLETE | 質問応答、複数ファイル比較 |
| 🛠️ その他 | 要約、翻訳 |

## ファイル構成

```
├── streamlit_app.py    # メインアプリケーション
├── snowflake.yml       # Snowflake CLI デプロイ設定
├── environment.yml     # Python 依存関係
├── pyproject.toml      # プロジェクト設定
├── .gitignore          # Git 除外設定
└── README.md           # このファイル
```

## 制限事項

| 項目 | 制限 |
|------|------|
| AI_COMPLETE | モデルごとにファイルサイズ・形式制限あり |
| AI_PARSE_DOCUMENT | 画像抽出は PDF のみ対応 |
| AI_EXTRACT | 100MB 以下 |

## 参考ドキュメント

- [AI_COMPLETE with documents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-complete-document-intelligence)
- [AI_PARSE_DOCUMENT](https://docs.snowflake.com/en/sql-reference/functions/ai_parse_document)
- [AI_EXTRACT](https://docs.snowflake.com/en/sql-reference/functions/ai_extract)
- [Cortex AI Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions)
- [Streamlit in Snowflake](https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit)

## ライセンス

MIT License
