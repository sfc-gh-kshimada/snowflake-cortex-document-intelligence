import streamlit as st
import pandas as pd
import json
import base64
from datetime import datetime

st.set_page_config(
    page_title="Document Extraction PoC",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

STAGE_NAME = "DEMOAPP.DOCUMENT_EXTRACTION.papers"

FILE_LIMITS = {
    "gemini-3-pro": {
        "max_size_mb": 10,
        "supported_formats": [".pdf", ".txt", ".md"],
        "max_files": 20,
        "context_window": "1M tokens",
        "description": "PDF専用・大容量対応 (最大10MB, 900ページ)"
    },
    "claude-sonnet-4-5": {
        "max_size_mb": 4.5,
        "supported_formats": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".xhtml"],
        "max_files": 5,
        "context_window": "200K tokens",
        "description": "Claude 4.5 Sonnet - バランス型"
    },
    "claude-opus-4-5": {
        "max_size_mb": 4.5,
        "supported_formats": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".xhtml"],
        "max_files": 5,
        "context_window": "200K tokens",
        "description": "Claude 4.5 Opus - 高精度"
    },
    "claude-haiku-4-5": {
        "max_size_mb": 4.5,
        "supported_formats": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".xhtml"],
        "max_files": 5,
        "context_window": "200K tokens",
        "description": "Claude 4.5 Haiku - 高速・低コスト"
    },
    "claude-4-sonnet": {
        "max_size_mb": 4.5,
        "supported_formats": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".xhtml"],
        "max_files": 5,
        "context_window": "200K tokens",
        "description": "Claude 4 Sonnet"
    },
    "claude-4-opus": {
        "max_size_mb": 4.5,
        "supported_formats": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".xhtml"],
        "max_files": 5,
        "context_window": "200K tokens",
        "description": "Claude 4 Opus"
    },
    "claude-3-7-sonnet": {
        "max_size_mb": 4.5,
        "supported_formats": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".xhtml"],
        "max_files": 5,
        "context_window": "200K tokens",
        "description": "Claude 3.7 Sonnet"
    }
}

PARSE_SUPPORTED = [".pdf", ".docx", ".pptx", ".doc", ".ppt", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"]
EXTRACT_SUPPORTED = [".pdf", ".png", ".pptx", ".ppt", ".eml", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".htm", ".html", ".txt", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".md"]


def get_snowflake_session():
    return st.connection("snowflake").session()


def get_file_extension(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_file(file, function_type: str, model: str = None) -> tuple[bool, str]:
    file_ext = get_file_extension(file.name)
    file_size_mb = file.size / (1024 * 1024)
    
    if function_type == "AI_COMPLETE":
        if model not in FILE_LIMITS:
            return False, f"未対応のモデル: {model}"
        limits = FILE_LIMITS[model]
        if file_ext not in limits["supported_formats"]:
            return False, f"{model} は {file_ext} 形式に対応していません。対応形式: {', '.join(limits['supported_formats'])}"
        if file_size_mb > limits["max_size_mb"]:
            return False, f"ファイルサイズ ({file_size_mb:.1f}MB) が {model} の上限 ({limits['max_size_mb']}MB) を超えています"
    
    elif function_type == "AI_PARSE_DOCUMENT":
        if file_ext not in PARSE_SUPPORTED:
            return False, f"AI_PARSE_DOCUMENT は {file_ext} 形式に対応していません。対応形式: {', '.join(PARSE_SUPPORTED)}"
    
    elif function_type == "AI_EXTRACT":
        if file_ext not in EXTRACT_SUPPORTED:
            return False, f"AI_EXTRACT は {file_ext} 形式に対応していません。対応形式: {', '.join(EXTRACT_SUPPORTED)}"
        if file_size_mb > 100:
            return False, f"ファイルサイズ ({file_size_mb:.1f}MB) が上限 (100MB) を超えています"
    
    return True, ""


def upload_to_stage(file, session) -> str:
    file_bytes = file.read()
    file.seek(0)
    
    session.file.put_stream(
        file,
        f"@{STAGE_NAME}/{file.name}",
        auto_compress=False,
        overwrite=True
    )
    return file.name


def run_ai_parse_document(session, filename: str, options: dict) -> dict:
    options_json = json.dumps(options)
    query = f"""
    SELECT AI_PARSE_DOCUMENT(
        TO_FILE('@{STAGE_NAME}', '{filename}'),
        PARSE_JSON('{options_json}')
    ) AS result
    """
    result = session.sql(query).collect()
    return result[0]["RESULT"] if result else None


def run_ai_extract(session, filename: str, response_format: dict) -> dict:
    format_json = json.dumps(response_format).replace("'", "''")
    query = f"""
    SELECT AI_EXTRACT(
        file => TO_FILE('@{STAGE_NAME}', '{filename}'),
        responseFormat => PARSE_JSON('{format_json}')
    ) AS result
    """
    result = session.sql(query).collect()
    return result[0]["RESULT"] if result else None


def run_ai_complete(session, filename: str, prompt: str, model: str) -> str:
    prompt_escaped = prompt.replace("'", "''")
    query = f"""
    SELECT AI_COMPLETE(
        MODEL => '{model}',
        PROMPT => PROMPT(
            '{prompt_escaped} {{0}}',
            TO_FILE('@{STAGE_NAME}', '{filename}')
        )
    ) AS result
    """
    result = session.sql(query).collect()
    return result[0]["RESULT"] if result else None


def run_ai_summarize(session, text: str) -> str:
    text_escaped = text.replace("'", "''").replace("\\", "\\\\")
    if len(text_escaped) > 50000:
        text_escaped = text_escaped[:50000]
    query = f"SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{text_escaped}') AS result"
    result = session.sql(query).collect()
    return result[0]["RESULT"] if result else None


def run_ai_translate(session, text: str, target_lang: str) -> str:
    text_escaped = text.replace("'", "''").replace("\\", "\\\\")
    if len(text_escaped) > 50000:
        text_escaped = text_escaped[:50000]
    query = f"SELECT SNOWFLAKE.CORTEX.TRANSLATE('{text_escaped}', 'en', '{target_lang}') AS result"
    result = session.sql(query).collect()
    return result[0]["RESULT"] if result else None


def display_images_from_result(result: dict, session=None, filename: str = None):
    if isinstance(result, str):
        result = json.loads(result)
    
    images = []
    if "images" in result:
        images = result["images"]
    elif "pages" in result:
        for page in result["pages"]:
            if "images" in page:
                for img in page["images"]:
                    img["page"] = page.get("index", 0) + 1
                    images.append(img)
    
    if images:
        st.subheader(f"🖼️ 抽出された画像 ({len(images)}枚)")
        
        num_cols = 3
        rows = [images[i:i+num_cols] for i in range(0, len(images), num_cols)]
        
        for row_idx, row in enumerate(rows):
            cols = st.columns(num_cols)
            for col_idx, img in enumerate(row):
                with cols[col_idx]:
                    img_idx = row_idx * num_cols + col_idx
                    page_num = img.get("page", "?")
                    img_id = img.get("id", img_idx + 1)
                    
                    if "image_base64" in img:
                        base64_data = img["image_base64"]
                        if base64_data.startswith("data:"):
                            base64_data = base64_data.split(",", 1)[1]
                        
                        st.image(
                            base64.b64decode(base64_data),
                            caption=f"Image {img_id} (Page {page_num})",
                            use_column_width=True
                        )
                        
                        explain_key = f"img_explain_{img_idx}"
                        
                        if session and filename:
                            if st.button("🔍 解説", key=f"explain_img_{img_idx}"):
                                with st.spinner("画像を解説中..."):
                                    try:
                                        prompt = f"このドキュメントのPage {page_num}にある画像(ID: {img_id})について、文脈を踏まえて詳しく解説してください。図表の場合は、データの意味や傾向も説明してください。"
                                        explain_result = run_ai_complete(session, filename, prompt, "gemini-3-pro")
                                        if isinstance(explain_result, str):
                                            explain_result = explain_result.replace("\\n", "\n").strip('"')
                                        st.session_state[explain_key] = explain_result
                                    except Exception as e:
                                        st.session_state[explain_key] = f"解説エラー: {e}"
                            
                            if explain_key in st.session_state:
                                st.info(st.session_state[explain_key])


with st.sidebar:
    st.title("📄 Document Extraction")
    st.caption("Snowflake Cortex AI Functions")
    
    st.divider()
    
    uploaded_file = st.file_uploader(
        "ファイルをアップロード",
        type=["pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "png", "jpg", "jpeg", "txt", "md", "csv"],
        help="PDF, Word, Excel, PowerPoint, 画像ファイルに対応"
    )
    
    if uploaded_file:
        file_ext = get_file_extension(uploaded_file.name)
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        st.success(f"✅ {uploaded_file.name}")
        st.caption(f"サイズ: {file_size_mb:.2f} MB | 形式: {file_ext}")
        
        with st.expander("📊 対応状況", expanded=False):
            st.markdown("**AI_PARSE_DOCUMENT**")
            if file_ext in PARSE_SUPPORTED:
                st.markdown("✅ 対応")
            else:
                st.markdown(f"❌ 非対応 ({file_ext})")
            
            st.markdown("**AI_EXTRACT**")
            if file_ext in EXTRACT_SUPPORTED:
                st.markdown("✅ 対応")
            else:
                st.markdown(f"❌ 非対応 ({file_ext})")
            
            st.markdown("**AI_COMPLETE**")
            for model, limits in FILE_LIMITS.items():
                if file_ext in limits["supported_formats"] and file_size_mb <= limits["max_size_mb"]:
                    st.markdown(f"✅ {model}")
                else:
                    reasons = []
                    if file_ext not in limits["supported_formats"]:
                        reasons.append("形式非対応")
                    if file_size_mb > limits["max_size_mb"]:
                        reasons.append(f"サイズ超過")
                    st.markdown(f"❌ {model} ({', '.join(reasons)})")
    
    st.divider()
    st.caption("Snowflake Cortex AI PoC")
    st.caption(f"検証日: {datetime.now().strftime('%Y-%m-%d')}")


st.title("📄 ドキュメント抽出 PoC")
st.markdown("Snowflake Cortex AI 関数を使用して、PDF/Word/Excel/PowerPoint からテキスト・図表・画像を抽出します。")

if not uploaded_file:
    st.info("👈 サイドバーからファイルをアップロードしてください")
    
    with st.expander("📚 対応関数と機能", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### AI_PARSE_DOCUMENT")
            st.markdown("""
            - テキスト構造化抽出
            - ページ分割処理
            - 画像抽出 (Base64)
            - レイアウト保持
            """)
            st.caption("対応: PDF, DOCX, PPTX, 画像")
        
        with col2:
            st.markdown("### AI_EXTRACT")
            st.markdown("""
            - エンティティ抽出
            - テーブル抽出
            - カスタムスキーマ
            - 構造化JSON出力
            """)
            st.caption("対応: PDF, DOCX, XLSX, 画像等")
        
        with col3:
            st.markdown("### AI_COMPLETE")
            st.markdown("""
            - 自然言語Q&A
            - 図表解釈
            - 要約・翻訳
            - クロスページ分析
            """)
            st.caption("対応: モデルにより異なる")
    
    st.stop()

session = get_snowflake_session()

with st.spinner("ファイルをアップロード中..."):
    try:
        filename = upload_to_stage(uploaded_file, session)
        st.toast(f"✅ {filename} をステージにアップロードしました", icon="✅")
    except Exception as e:
        st.error(f"アップロードエラー: {e}")
        st.stop()

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 AI_PARSE_DOCUMENT",
    "📊 AI_EXTRACT", 
    "💬 AI_COMPLETE",
    "🛠️ その他の関数"
])

with tab1:
    st.header("🔍 AI_PARSE_DOCUMENT")
    st.markdown("ドキュメントをパースし、テキスト・画像・構造を抽出します。")
    
    file_ext = get_file_extension(uploaded_file.name)
    valid, error_msg = validate_file(uploaded_file, "AI_PARSE_DOCUMENT")
    
    if not valid:
        st.error(f"⚠️ {error_msg}")
    else:
        col1, col2 = st.columns(2)
        with col1:
            parse_mode = st.selectbox(
                "パースモード",
                ["LAYOUT", "OCR"],
                help="LAYOUT: テキスト+構造, OCR: テキストのみ"
            )
        with col2:
            page_split = st.checkbox("ページ分割", value=True, help="ページごとに結果を分割")
        
        extract_images = st.checkbox("画像抽出", value=False, help="埋め込み画像をBase64で抽出 (PDF専用)")
        
        if st.button("🚀 パース実行", key="parse_btn", type="primary"):
            options = {"mode": parse_mode}
            if page_split:
                options["page_split"] = True
            if extract_images and file_ext == ".pdf":
                options["extract_images"] = True
            
            with st.spinner("パース処理中..."):
                try:
                    result = run_ai_parse_document(session, filename, options)
                    
                    if isinstance(result, str):
                        result = json.loads(result)
                    
                    st.session_state["parse_result"] = result
                    st.session_state["parse_filename"] = filename
                    st.session_state["parse_extract_images"] = extract_images
                    
                except Exception as e:
                    st.error(f"エラー: {e}")
        
        if "parse_result" in st.session_state and st.session_state.get("parse_filename") == filename:
            result = st.session_state["parse_result"]
            stored_extract_images = st.session_state.get("parse_extract_images", False)
            
            if "errorInformation" in result:
                st.error(f"エラー: {result['errorInformation']}")
            else:
                st.success("✅ パース完了")
                
                if "pages" in result:
                    st.subheader(f"📑 ページ数: {len(result['pages'])}")
                    
                    for page in result["pages"]:
                        page_num = page.get("index", 0) + 1
                        content = page.get("content", "")
                        with st.expander(f"📄 ページ {page_num} ({len(content):,} 文字)", expanded=(page_num == 1)):
                            st.text_area(
                                label=f"ページ {page_num} 内容",
                                value=content,
                                height=400,
                                label_visibility="collapsed",
                                key=f"page_content_{page_num}"
                            )
                else:
                    content = result.get("content", "")
                    st.subheader(f"📄 抽出テキスト ({len(content):,} 文字)")
                    st.text_area(
                        label="抽出テキスト",
                        value=content,
                        height=500,
                        label_visibility="collapsed",
                        key="full_content"
                    )
                
                if stored_extract_images:
                    display_images_from_result(result, session, filename)
                
                with st.expander("🔧 生のJSON出力"):
                    st.json(result)


with tab2:
    st.header("📊 AI_EXTRACT")
    st.markdown("ドキュメントから特定の情報を構造化抽出します。")
    
    valid, error_msg = validate_file(uploaded_file, "AI_EXTRACT")
    
    if not valid:
        st.error(f"⚠️ {error_msg}")
    else:
        extract_type = st.radio(
            "抽出タイプ",
            ["エンティティ抽出", "テーブル抽出", "カスタムスキーマ"],
            horizontal=True
        )
        
        if extract_type == "エンティティ抽出":
            st.markdown("**抽出するエンティティを定義:**")
            
            col1, col2 = st.columns(2)
            with col1:
                entity1_name = st.text_input("エンティティ1 名前", "title")
                entity1_desc = st.text_input("エンティティ1 説明", "ドキュメントのタイトル")
            with col2:
                entity2_name = st.text_input("エンティティ2 名前", "authors")
                entity2_desc = st.text_input("エンティティ2 説明", "著者名のリスト")
            
            entity3_name = st.text_input("エンティティ3 名前 (任意)", "key_findings")
            entity3_desc = st.text_input("エンティティ3 説明 (任意)", "主要な発見や結論")
            
            if st.button("🚀 エンティティ抽出", key="extract_entity_btn", type="primary"):
                response_format = {
                    entity1_name: entity1_desc,
                    entity2_name: entity2_desc
                }
                if entity3_name:
                    response_format[entity3_name] = entity3_desc
                
                with st.spinner("抽出中..."):
                    try:
                        result = run_ai_extract(session, filename, response_format)
                        if isinstance(result, str):
                            result = json.loads(result)
                        
                        if result.get("error"):
                            st.error(f"エラー: {result['error']}")
                        else:
                            st.success("✅ 抽出完了")
                            response = result.get("response", {})
                            
                            for key, value in response.items():
                                st.subheader(f"📌 {key}")
                                if isinstance(value, list):
                                    for item in value:
                                        st.markdown(f"- {item}")
                                else:
                                    st.markdown(value)
                            
                            with st.expander("🔧 生のJSON出力"):
                                st.json(result)
                    except Exception as e:
                        st.error(f"エラー: {e}")
        
        elif extract_type == "テーブル抽出":
            st.markdown("**抽出するテーブルのカラムを定義:**")
            
            table_desc = st.text_input("テーブルの説明", "データテーブル")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                col1_name = st.text_input("カラム1", "item")
                col1_desc = st.text_input("カラム1説明", "項目名")
            with col2:
                col2_name = st.text_input("カラム2", "value")
                col2_desc = st.text_input("カラム2説明", "数値")
            with col3:
                col3_name = st.text_input("カラム3 (任意)", "")
                col3_desc = st.text_input("カラム3説明 (任意)", "")
            
            if st.button("🚀 テーブル抽出", key="extract_table_btn", type="primary"):
                columns = {
                    col1_name: {"description": col1_desc, "type": "array"},
                    col2_name: {"description": col2_desc, "type": "array"}
                }
                column_ordering = [col1_name, col2_name]
                
                if col3_name:
                    columns[col3_name] = {"description": col3_desc, "type": "array"}
                    column_ordering.append(col3_name)
                
                response_format = {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "extracted_table": {
                                "description": table_desc,
                                "type": "object",
                                "column_ordering": column_ordering,
                                "properties": columns
                            }
                        }
                    }
                }
                
                with st.spinner("テーブル抽出中..."):
                    try:
                        result = run_ai_extract(session, filename, response_format)
                        if isinstance(result, str):
                            result = json.loads(result)
                        
                        if result.get("error"):
                            st.error(f"エラー: {result['error']}")
                        else:
                            st.success("✅ テーブル抽出完了")
                            
                            table_data = result.get("response", {}).get("extracted_table", {})
                            if table_data:
                                df = pd.DataFrame(table_data)
                                st.dataframe(df, use_container_width=True)
                                
                                csv = df.to_csv(index=False)
                                st.download_button(
                                    "📥 CSVダウンロード",
                                    csv,
                                    f"extracted_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    "text/csv"
                                )
                            
                            with st.expander("🔧 生のJSON出力"):
                                st.json(result)
                    except Exception as e:
                        st.error(f"エラー: {e}")
        
        else:
            st.markdown("**カスタムJSONスキーマを入力:**")
            custom_schema = st.text_area(
                "JSON スキーマ",
                value=json.dumps({
                    "title": "ドキュメントのタイトル",
                    "summary": "100文字以内の要約",
                    "keywords": "キーワードのリスト"
                }, ensure_ascii=False, indent=2),
                height=200
            )
            
            if st.button("🚀 カスタム抽出", key="extract_custom_btn", type="primary"):
                try:
                    response_format = json.loads(custom_schema)
                    with st.spinner("抽出中..."):
                        result = run_ai_extract(session, filename, response_format)
                        if isinstance(result, str):
                            result = json.loads(result)
                        
                        st.success("✅ 抽出完了")
                        st.json(result.get("response", result))
                except json.JSONDecodeError as e:
                    st.error(f"JSONパースエラー: {e}")
                except Exception as e:
                    st.error(f"エラー: {e}")


with tab3:
    st.header("💬 AI_COMPLETE")
    st.markdown("LLMを使用してドキュメントに関する質問に回答します。")
    
    model = st.selectbox(
        "モデル選択",
        list(FILE_LIMITS.keys()),
        format_func=lambda x: f"{x} - {FILE_LIMITS[x]['description']}"
    )
    
    valid, error_msg = validate_file(uploaded_file, "AI_COMPLETE", model)
    
    if not valid:
        st.error(f"⚠️ {error_msg}")
        
        st.info("💡 **代替案**: AI_PARSE_DOCUMENT でテキストを抽出し、その結果に対して AI_COMPLETE を実行できます。")
    else:
        prompt_type = st.radio(
            "プロンプトタイプ",
            ["プリセット", "カスタム"],
            horizontal=True
        )
        
        if prompt_type == "プリセット":
            preset = st.selectbox(
                "プリセットを選択",
                [
                    "このドキュメントを日本語で要約してください。",
                    "このドキュメントに含まれる全ての図表のキャプションをリストアップしてください。",
                    "このドキュメントの主要な発見・結論を箇条書きで説明してください。",
                    "このドキュメントに含まれるテーブルのデータをJSON形式で抽出してください。",
                    "このドキュメントの構成（セクション構成）を説明してください。"
                ]
            )
            prompt = preset
        else:
            prompt = st.text_area(
                "プロンプトを入力",
                value="このドキュメントについて説明してください。",
                height=100,
                help="ドキュメントは自動的にプロンプトに添付されます"
            )
        
        if st.button("🚀 質問を実行", key="complete_btn", type="primary"):
            with st.spinner(f"{model} で処理中..."):
                try:
                    result = run_ai_complete(session, filename, prompt, model)
                    st.success("✅ 完了")
                    st.markdown("### 回答")
                    if isinstance(result, str):
                        result = result.replace("\\n", "\n").strip('"')
                    st.markdown(result)
                except Exception as e:
                    error_str = str(e)
                    if "exceeds the limit" in error_str:
                        st.error(f"⚠️ ファイルサイズが {model} の上限を超えています。より小さいファイルを使用するか、Gemini モデルを試してください。")
                    elif "unsupported" in error_str.lower():
                        st.error(f"⚠️ このファイル形式は {model} でサポートされていません。")
                    else:
                        st.error(f"エラー: {e}")


with tab4:
    st.header("🛠️ その他の Cortex AI 関数")
    st.markdown("追加の AI 関数でドキュメントを処理します。")
    
    st.subheader("📝 AI_SUMMARIZE")
    st.markdown("テキストを自動要約します。まず AI_PARSE_DOCUMENT でテキストを抽出してから使用します。")
    
    if st.button("📄 テキスト抽出 → 要約", key="summarize_btn"):
        with st.spinner("テキスト抽出中..."):
            try:
                result = run_ai_parse_document(session, filename, {"mode": "LAYOUT"})
                if isinstance(result, str):
                    result = json.loads(result)
                
                content = result.get("content", "")
                if not content:
                    st.warning("テキストを抽出できませんでした")
                else:
                    st.info(f"抽出されたテキスト: {len(content):,} 文字")
                    
                    with st.spinner("要約中..."):
                        summary = run_ai_summarize(session, content)
                        st.success("✅ 要約完了")
                        st.markdown("### 要約")
                        st.markdown(summary)
            except Exception as e:
                st.error(f"エラー: {e}")
    
    st.divider()
    
    st.subheader("🌐 AI_TRANSLATE")
    st.markdown("テキストを翻訳します。まず AI_PARSE_DOCUMENT でテキストを抽出してから使用します。")
    
    target_lang = st.selectbox(
        "翻訳先言語",
        ["ja", "en", "zh", "ko", "de", "fr", "es"],
        format_func=lambda x: {"ja": "日本語", "en": "英語", "zh": "中国語", "ko": "韓国語", "de": "ドイツ語", "fr": "フランス語", "es": "スペイン語"}[x]
    )
    
    if st.button("📄 テキスト抽出 → 翻訳", key="translate_btn"):
        with st.spinner("テキスト抽出中..."):
            try:
                result = run_ai_parse_document(session, filename, {"mode": "LAYOUT"})
                if isinstance(result, str):
                    result = json.loads(result)
                
                content = result.get("content", "")
                if not content:
                    st.warning("テキストを抽出できませんでした")
                else:
                    content_preview = content[:10000]
                    st.info(f"翻訳対象: {len(content_preview):,} 文字 (最初の10,000文字)")
                    
                    with st.spinner("翻訳中..."):
                        translated = run_ai_translate(session, content_preview, target_lang)
                        st.success("✅ 翻訳完了")
                        st.markdown("### 翻訳結果")
                        st.markdown(translated)
            except Exception as e:
                st.error(f"エラー: {e}")
    
    st.divider()
    
    st.subheader("📊 複数ファイル比較 (AI_COMPLETE)")
    st.markdown("ステージ上の既存ファイルと比較分析を行います。")
    
    try:
        files_df = session.sql(f"LIST @{STAGE_NAME}").to_pandas()
        if not files_df.empty:
            name_col = [c for c in files_df.columns if c.lower() == "name"][0]
            files_df["filename"] = files_df[name_col].apply(lambda x: x.split("/")[-1])
            available_files = files_df["filename"].tolist()
            
            compare_file = st.selectbox(
                "比較対象ファイル",
                [f for f in available_files if f != filename],
                help="現在アップロードしたファイルと比較するファイルを選択"
            )
            
            if compare_file and st.button("🔄 ファイル比較", key="compare_btn"):
                with st.spinner("比較分析中..."):
                    try:
                        compare_prompt = f"""
                        以下の2つのドキュメントを比較してください:
                        1. {{0}} 
                        2. {{1}}
                        
                        比較ポイント:
                        - 主題・目的の違い
                        - 内容の共通点と相違点
                        - 使用されている図表の種類
                        
                        結果はJSON形式で出力してください。
                        """
                        query = f"""
                        SELECT AI_COMPLETE(
                            MODEL => 'gemini-3-pro',
                            PROMPT => PROMPT(
                                '{compare_prompt.replace("'", "''")}',
                                TO_FILE('@{STAGE_NAME}', '{filename}'),
                                TO_FILE('@{STAGE_NAME}', '{compare_file}')
                            )
                        ) AS result
                        """
                        result = session.sql(query).collect()
                        st.success("✅ 比較完了")
                        st.markdown("### 比較結果")
                        compare_result = result[0]["RESULT"]
                        if isinstance(compare_result, str):
                            compare_result = compare_result.replace("\\n", "\n").strip('"')
                        st.markdown(compare_result)
                    except Exception as e:
                        st.error(f"エラー: {e}")
        else:
            st.info("ステージにファイルがありません")
    except Exception as e:
        st.warning(f"ファイル一覧の取得に失敗: {e}")


st.divider()
with st.expander("ℹ️ 関数リファレンス", expanded=False):
    st.markdown("""
    ### AI_PARSE_DOCUMENT
    - **用途**: ドキュメントからテキスト・構造・画像を抽出
    - **対応形式**: PDF, DOCX, PPTX, 画像 (PNG, JPG, TIFF等)
    - **オプション**: `mode` (LAYOUT/OCR), `page_split`, `extract_images`, `page_filter`
    
    ### AI_EXTRACT
    - **用途**: 構造化データの抽出 (エンティティ、テーブル)
    - **対応形式**: PDF, DOCX, XLSX, 画像等 (100MB以下)
    - **出力**: JSON形式
    
    ### AI_COMPLETE (Document Intelligence)
    - **用途**: ドキュメントに対する自然言語Q&A
    - **モデル別制限**:
      - `gemini-3-pro`: PDF専用, 最大10MB, 20ファイル/プロンプト
      - `claude-4-sonnet/opus`: PDF/Word/Excel対応, 最大4.5MB, 5ファイル/プロンプト
    
    ### AI_SUMMARIZE / AI_TRANSLATE
    - **用途**: テキストの要約・翻訳
    - **入力**: テキスト文字列 (AI_PARSE_DOCUMENTの出力を使用)
    """)
